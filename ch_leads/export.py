"""Build the Excel workbook: Summary tab + one tab per industry."""
import datetime
import os

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from db import ROOT, connect
from industries import INDUSTRIES, MIN_INCORPORATION_YEAR, MIN_TURNOVER, fit_text, icp_reject

CH_URL = "https://find-and-update.company-information.service.gov.uk/company/{}"
COLUMNS = [
    ("Company name", 34), ("Company number", 12), ("Companies House link", 22), ("Directors", 9), ("Turnover (£)", 13), ("Turnover basis", 26), ("Employees", 10),
    ("Director names", 32), ("Owners (PSC)", 28), ("Website", 30), ("Website match", 11), ("Phone", 16), ("Email", 28),
    ("Registered address", 40), ("Incorporated", 12), ("Accounts type", 18), ("SIC codes", 40),
    ("Overview", 60), ("Why it's a fit", 70), ("Verified contactable", 12), ("Flags", 24),
]
MAX_ROWS = 1_000_000
HEADER_FILL = PatternFill("solid", fgColor="1F3A5F")

QUERY = """
SELECT c.*, o.n_directors, o.names, p.status AS ch_status, p.undeliverable, p.in_dispute,
       p.insolvency, p.accounts_overdue, p.confstmt_overdue, p.owner_type, p.owners,
       w.url, w.match, w.title, w.description, w.phone, w.email,
       f.est_turnover, f.basis, f.made_up, f.employees
FROM companies c JOIN officers o ON o.number = c.number
JOIN financials f ON f.number = c.number
LEFT JOIN profiles p ON p.number = c.number
LEFT JOIN websites w ON w.number = c.number
WHERE o.n_directors IN (1, 2) AND ('|' || c.industries || '|') LIKE ?
  AND CAST(substr(c.incorporated, 7, 4) AS INTEGER) >= {year}
  AND f.est_turnover >= {turnover}
""".format(year=MIN_INCORPORATION_YEAR, turnover=MIN_TURNOVER)
BATCH_FILTER = """ AND w.number IS NOT NULL
  AND (c.number NOT IN (SELECT number FROM batched) OR c.number IN (SELECT number FROM batched WHERE batch = ?))"""


def overview(r):
    acts = "; ".join(s.split(" - ", 1)[-1] for s in (r["sic"] or "").split(" | ") if s)
    parts = [acts.rstrip(".") + "."]
    site = r["description"] or r["title"]
    if site:
        parts.append(f"Website: \"{site}\"")
    year = (r["incorporated"] or "")[-4:]
    if year:
        parts.append(f"Trading since {year}" + (f", based in {r['town'].title()}." if r["town"] else "."))
    return " ".join(parts)


def verify(r):
    flags = []
    if r["ch_status"] is None:
        return "Not checked", ""
    if r["ch_status"] != "active":
        flags.append(f"status {r['ch_status']}")
    if r["undeliverable"]:
        flags.append("registered office undeliverable")
    if r["in_dispute"]:
        flags.append("registered office in dispute")
    if r["insolvency"]:
        flags.append("insolvency history")
    if r["owner_type"] == "corporate":
        flags.append(f"subsidiary of {r['owners']}")
    hard = bool(flags)
    if r["accounts_overdue"]:
        flags.append("accounts overdue")
    if r["confstmt_overdue"]:
        flags.append("confirmation statement overdue")
    return ("No" if hard else "Yes"), "; ".join(flags)


def build(path=None, batch=None):
    """Full workbook, or with batch=N only leads assigned to batch N (new ones first)."""
    con = connect()
    path = path or os.path.join(ROOT, "output", f"bill_pay_leads_{datetime.date.today():%Y-%m-%d}.xlsx")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    wb = Workbook(write_only=True)
    summary = wb.create_sheet("Summary")
    summary_rows = []
    for ind in INDUSTRIES:
        total = con.execute("SELECT count(*) FROM companies WHERE ('|'||industries||'|') LIKE ? "
                            "AND CAST(substr(incorporated,7,4) AS INTEGER) >= ?",
                            (f"%|{ind}|%", MIN_INCORPORATION_YEAR)).fetchone()[0]
        checked = con.execute("SELECT count(*) FROM companies c JOIN officers o USING(number) "
                              "WHERE ('|'||c.industries||'|') LIKE ? AND CAST(substr(c.incorporated,7,4) AS INTEGER) >= ?",
                              (f"%|{ind}|%", MIN_INCORPORATION_YEAR)).fetchone()[0]
        rows = []
        q, args = (QUERY + BATCH_FILTER, (f"%|{ind}|%", batch)) if batch else (QUERY, (f"%|{ind}|%",))
        for r in con.execute(q, args):
            ok, flags = verify(r)
            if ok == "No":
                continue
            if icp_reject(ind, r["name"], (r["sic"] or "").split(" | "), bool(r["url"])):
                continue
            rows.append(r)
        if batch:
            con.executemany("INSERT OR IGNORE INTO batched VALUES (?,?)", [(r["number"], batch) for r in rows])
            con.commit()
        rows.sort(key=lambda r: (r["n_directors"], 0 if r["match"] == "Confirmed" else 1 if r["url"] else 2,
                                 r["name"]))
        for part in range(0, max(len(rows), 1), MAX_ROWS):
            title = ind if part == 0 else f"{ind} ({part // MAX_ROWS + 1})"
            ws = wb.create_sheet(title[:31])
            for i, (_, w) in enumerate(COLUMNS, 1):
                ws.column_dimensions[get_column_letter(i)].width = w
            ws.freeze_panes = "A2"
            ws.auto_filter.ref = f"A1:{get_column_letter(len(COLUMNS))}{len(rows[part:part + MAX_ROWS]) + 1}"
            ws.append([_hdr(ws, c) for c, _ in COLUMNS])
            for r in rows[part:part + MAX_ROWS]:
                ok, flags = verify(r)
                ws.append([
                    r["name"], r["number"], _link(ws, CH_URL.format(r["number"]), "View on Companies House"),
                    r["n_directors"], round(r["est_turnover"] or 0, -3), r["basis"] + _year(r["made_up"]),
                    int(r["employees"]) if r["employees"] is not None else "", r["names"], r["owners"] or "", _link(ws, r["url"], r["url"]) if r["url"] else "",
                    r["match"] if r["url"] else "", r["phone"] or "", r["email"] or "", r["address"],
                    r["incorporated"], (r["account_category"] or "").title(), r["sic"], overview(r),
                    fit_text(ind, r["n_directors"]), ok, flags,
                ])
        one = sum(1 for r in rows if r["n_directors"] == 1)
        web = sum(1 for r in rows if r["url"])
        summary_rows.append([ind, total, checked, len(rows), one, len(rows) - one, web])
    summary.column_dimensions["A"].width = 26
    for col in "BCDEFG":
        summary.column_dimensions[col].width = 18
    lead_hdr = f"Leads in batch {batch}" if batch else "Leads (1-2 directors)"
    summary.append([_hdr(summary, h) for h in ("Industry", "Active candidates (SIC match)",
                    "Director count checked (all batches)", lead_hdr, "1 director", "2 directors",
                    "Website found")])
    for row in summary_rows:
        summary.append(row)
    summary.append([])
    summary.append([f"Generated {datetime.datetime.now():%Y-%m-%d %H:%M} from Companies House data. "
                    f"Leads are companies incorporated {MIN_INCORPORATION_YEAR} or later with filed or estimated turnover of £{MIN_TURNOVER:,}+ (estimates use industry ratios from companies that file turnover). They exclude dormant companies and any with insolvency history or an "
                    "undeliverable / disputed registered office, and subsidiaries owned by another company (not owner-led). 'Probable' websites match the "
                    "company name but the company number wasn't found on the site."])
    wb.save(path)
    return path, summary_rows


def _year(made_up):
    return f" (accounts to {made_up[4:6]}/{made_up[:4]})" if made_up else ""


def _hdr(ws, text):
    from openpyxl.cell import WriteOnlyCell
    c = WriteOnlyCell(ws, value=text)
    c.font = Font(bold=True, color="FFFFFF")
    c.fill = HEADER_FILL
    c.alignment = Alignment(wrap_text=True, vertical="center")
    return c


def _link(ws, url, text):
    from openpyxl.cell import WriteOnlyCell
    c = WriteOnlyCell(ws, value=text)
    c.hyperlink = url
    c.font = Font(color="0563C1", underline="single")
    return c
