"""Turnover from Companies House accounts bulk data (iXBRL), filed or estimated.

Small companies rarely publish turnover, so where it isn't filed we estimate it
from figures they do file (employees, debtors, current assets), using ratios
calibrated on companies in the same industry that do file turnover.
"""
import os
import re
import statistics
import time
import zipfile

import requests

from db import DATA_DIR, connect

BASE = "https://download.companieshouse.gov.uk/"
MONTHLY_INDEX = BASE + "en_monthlyaccountsdata.html"
DAILY_INDEX = BASE + "en_accountsdata.html"
TAGS = {
    "TurnoverRevenue": "turnover",
    "AverageNumberEmployeesDuringPeriod": "employees",
    "TradeDebtorsTradeReceivables": "trade_debtors",
    "Debtors": "debtors",
    "CurrentAssets": "current_assets",
    "NetAssetsLiabilities": "net_assets",
}
FACT_RE = re.compile(r'<ix:nonFraction\b([^>]*)>(.*?)</ix:nonFraction>', re.S | re.I)
ATTR_RE = re.compile(r'(\w+(?::\w+)?)="([^"]*)"')
CONTEXT_RE = re.compile(r'<xbrli:context\b[^>]*id="([^"]+)"[^>]*>(.*?)</xbrli:context>', re.S | re.I)
DATE_RE = re.compile(r'<xbrli:(?:endDate|instant)>\s*(\d{4}-\d{2}-\d{2})', re.I)
NUM_RE = re.compile(r"_(\d{8}|[A-Z]{2}\d{6})_(\d{8})\.(?:html|xml)$", re.I)


def parse(doc):
    """Returns {field: value} for the latest period, or {} if nothing useful."""
    contexts = {}
    for cid, body in CONTEXT_RE.findall(doc):
        if "explicitMember" in body or "typedMember" in body:
            continue  # dimensional breakdown, not the company total
        d = DATE_RE.search(body)
        if d:
            contexts[cid] = d.group(1)
    if not contexts:
        return {}
    latest = max(contexts.values())
    out = {}
    for attrs, inner in FACT_RE.findall(doc):
        a = dict(ATTR_RE.findall(attrs))
        field = TAGS.get(a.get("name", "").split(":")[-1])
        if not field or field in out or contexts.get(a.get("contextRef")) != latest:
            continue
        text = re.sub(r"<[^>]+>", "", inner).strip()
        if "numdotcomma" in a.get("format", ""):
            text = text.replace(".", "").replace(",", ".")
        text = re.sub(r"[^\d.]", "", text.replace(",", ""))
        if not text or text == ".":
            if "zerodash" in a.get("format", "") or inner.strip() in ("-", "—"):
                text = "0"
            else:
                continue
        try:
            v = float(text)
            if field != "employees":  # headcounts are never scaled
                v *= 10 ** int(a.get("scale", "0") or 0)
        except ValueError:
            continue
        out[field] = -v if a.get("sign") == "-" else v
    if out:
        out["period_end"] = latest
    return out


def _links(index_url, pattern):
    html = requests.get(index_url, timeout=60).text
    seen = []
    for m in re.findall(pattern, html):
        if m not in seen:
            seen.append(m)
    return seen


def archives(months=12):
    monthly = _links(MONTHLY_INDEX, r"Accounts_Monthly_Data-[A-Za-z]+\d{4}\.zip")[-months:]
    daily = _links(DAILY_INDEX, r"Accounts_Bulk_Data-\d{4}-\d{2}-\d{2}\.zip")
    return monthly + daily


def _download(url, path, attempts=8):
    """Download with resume: large archives sometimes drop mid-transfer."""
    part = path + ".part"
    for attempt in range(attempts):
        have = os.path.getsize(part) if os.path.exists(part) else 0
        headers = {"Range": f"bytes={have}-"} if have else {}
        try:
            with requests.get(url, stream=True, timeout=600, headers=headers) as r:
                if r.status_code == 416:
                    break  # already complete
                r.raise_for_status()
                mode = "ab" if have and r.status_code == 206 else "wb"
                with open(part, mode) as f:
                    for chunk in r.iter_content(4 << 20):
                        f.write(chunk)
            break
        except requests.RequestException:
            if attempt == attempts - 1:
                raise
            time.sleep(5 * (attempt + 1))
    os.rename(part, path)


def ingest(name, wanted, con):
    """Download one archive, store financials for wanted company numbers, delete it."""
    done = con.execute("SELECT 1 FROM ingested WHERE name=?", (name,)).fetchone()
    if done:
        return 0
    path = os.path.join(DATA_DIR, name)
    _download(BASE + name, path)
    n = 0
    try:
        with zipfile.ZipFile(path) as z:
            for info in z.infolist():
                m = NUM_RE.search(info.filename)
                if not m or m.group(1).upper() not in wanted:
                    continue
                number, made_up = m.group(1).upper(), m.group(2)
                prev = con.execute("SELECT made_up FROM financials WHERE number=?", (number,)).fetchone()
                if prev and prev[0] >= made_up:
                    continue
                f = parse(z.read(info).decode("utf-8", "replace"))
                if not f:
                    continue
                con.execute(
                    "INSERT OR REPLACE INTO financials (number, made_up, turnover, employees, "
                    "trade_debtors, debtors, current_assets, net_assets) VALUES (?,?,?,?,?,?,?,?)",
                    (number, made_up, f.get("turnover"), f.get("employees"), f.get("trade_debtors"),
                     f.get("debtors"), f.get("current_assets"), f.get("net_assets")))
                n += 1
                if n % 2000 == 0:
                    con.commit()
    finally:
        os.remove(path)
    con.execute("INSERT OR REPLACE INTO ingested VALUES (?)", (name,))
    con.commit()
    return n


# --- estimation -------------------------------------------------------------

def calibrate(con, industries):
    """Median turnover ratios per industry from companies that file turnover."""
    ratios = {}
    for ind in list(industries) + ["*"]:
        like = "%" if ind == "*" else f"%|{ind}|%"
        rows = con.execute(
            "SELECT f.* FROM financials f JOIN companies c USING(number) "
            "WHERE f.turnover > 0 AND ('|'||c.industries||'|') LIKE ?", (like,)).fetchall()
        r = {}
        for key in ("employees", "trade_debtors", "debtors", "current_assets"):
            vals = [x["turnover"] / x[key] for x in rows if x[key] and x[key] > 0]
            if len(vals) >= 25:
                r[key] = statistics.median(vals)
        ratios[ind] = (r, len(rows))
    return ratios


def estimate(fin, ratios_for_industry, fallback):
    """Returns (turnover, basis) where basis is 'Filed' or 'Estimated (...)'."""
    if fin["turnover"]:
        return fin["turnover"], "Filed"
    ests, used = [], []
    for key, label in (("employees", "staff"), ("trade_debtors", "debtors"), ("debtors", "debtors"),
                       ("current_assets", "current assets")):
        ratio = ratios_for_industry.get(key) or fallback.get(key)
        if fin[key] and fin[key] > 0 and ratio and label not in used:
            ests.append(fin[key] * ratio)
            used.append(label)
    if not ests:
        return None, ""
    return statistics.median(ests), "Estimated from " + ", ".join(used)
