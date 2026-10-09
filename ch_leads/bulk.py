"""Download the Companies House bulk file and load matching active companies."""
import csv
import io
import os
import re
import zipfile

import requests

from db import DATA_DIR, connect
from industries import SIC_TO_INDUSTRIES

INDEX_URL = "https://download.companieshouse.gov.uk/en_output.html"
BASE = "https://download.companieshouse.gov.uk/"
KEEP_CATEGORIES = {"Private Limited Company", "Public Limited Company"}
DROP_ACCOUNTS = {"DORMANT", "NO ACCOUNTS FILED"}


def download(path=os.path.join(DATA_DIR, "bulk.zip")):
    if os.path.exists(path):
        return path
    html = requests.get(INDEX_URL, timeout=60).text
    name = re.search(r"BasicCompanyDataAsOneFile-[\d-]+\.zip", html).group(0)
    with requests.get(BASE + name, stream=True, timeout=600) as r:
        r.raise_for_status()
        with open(path + ".part", "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    os.rename(path + ".part", path)
    return path


def load(zip_path):
    con = connect()
    kept = 0
    with zipfile.ZipFile(zip_path) as z:
        inner = z.namelist()[0]
        with z.open(inner) as fh:
            reader = csv.reader(io.TextIOWrapper(fh, encoding="utf-8", errors="replace"))
            header = [h.strip() for h in next(reader)]
            ix = {h: i for i, h in enumerate(header)}
            batch = []
            for row in reader:
                if len(row) < len(header):
                    continue
                g = lambda k: row[ix[k]].strip()
                if g("CompanyStatus") != "Active" or g("CompanyCategory") not in KEEP_CATEGORIES:
                    continue
                if g("Accounts.AccountCategory") in DROP_ACCOUNTS:
                    continue
                sics = [g(f"SICCode.SicText_{i}") for i in range(1, 5)]
                sics = [s for s in sics if s and s[:5].isdigit()]
                inds = []
                for s in sics:
                    for ind in SIC_TO_INDUSTRIES.get(s[:5], []):
                        if ind not in inds:
                            inds.append(ind)
                if not inds:
                    continue
                addr = ", ".join(x for x in (g("RegAddress.AddressLine1"), g("RegAddress.AddressLine2"),
                                             g("RegAddress.PostTown"), g("RegAddress.County"),
                                             g("RegAddress.PostCode")) if x)
                batch.append((g("CompanyNumber"), g("CompanyName"), addr, g("RegAddress.PostTown"),
                              g("RegAddress.PostCode"), g("IncorporationDate"),
                              g("Accounts.AccountCategory"), " | ".join(sics), "|".join(inds),
                              g("Accounts.NextDueDate"), g("ConfStmtNextDueDate")))
                if len(batch) >= 5000:
                    kept += _flush(con, batch)
            kept += _flush(con, batch)
    return kept


def _flush(con, batch):
    n = len(batch)
    con.executemany("INSERT OR REPLACE INTO companies VALUES (?,?,?,?,?,?,?,?,?,?,?)", batch)
    con.commit()
    batch.clear()
    return n
