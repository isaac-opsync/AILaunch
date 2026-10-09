"""Bill Pay lead builder.

Stages (each resumable, all state in data/leads.db):
  python3 run.py bulk        # download + load Companies House bulk data
  python3 run.py officers    # director counts + profile checks via API (needs CH_API_KEY)
  python3 run.py websites    # find + verify websites for 1-2 director companies
  python3 run.py export      # write output/bill_pay_leads_<date>.xlsx (all leads so far)
  python3 run.py batch       # new leads since last batch -> batches/batch_NNN_<date>.xlsx,
                             # plus a resume snapshot in batches/state.sql.gz
  python3 run.py restore     # fresh machine: run `bulk` first, then this to resume

CH_API_KEY may hold several comma-separated keys to multiply throughput.
"""
import argparse
import datetime
import gzip
import os
import queue
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import bulk
import ch_api
import export
import websites
from db import connect
from industries import INDUSTRIES, MIN_INCORPORATION_YEAR

# Owner-managed SMEs first: small/abridged/total-exemption filers, then larger
# filers, then micro-entities; group and subsidiary filers last.
ACCOUNT_RANK = """CASE account_category
  WHEN 'SMALL' THEN 0 WHEN 'TOTAL EXEMPTION FULL' THEN 0 WHEN 'UNAUDITED ABRIDGED' THEN 0
  WHEN 'AUDITED ABRIDGED' THEN 0 WHEN 'TOTAL EXEMPTION SMALL' THEN 0
  WHEN 'FULL' THEN 1 WHEN 'MEDIUM' THEN 1 WHEN 'MICRO ENTITY' THEN 2 ELSE 3 END"""


def pending_queues(con, industries, limit):
    qs = {}
    for ind in industries:
        sql = (f"SELECT number FROM companies WHERE ('|'||industries||'|') LIKE ? "
               f"AND number NOT IN (SELECT number FROM officers) "
               f"AND CAST(substr(incorporated,7,4) AS INTEGER) >= {MIN_INCORPORATION_YEAR} "
               f"ORDER BY {ACCOUNT_RANK}, CAST(substr(incorporated,7,4) AS INTEGER) >= 2023, random()")
        if limit:
            sql += f" LIMIT {int(limit)}"
        qs[ind] = [r[0] for r in con.execute(sql, (f"%|{ind}|%",))]
    return qs


def round_robin(qs):
    seen = set()
    order = sorted(qs, key=lambda k: len(qs[k]))
    idx = {k: 0 for k in order}
    while True:
        progressed = False
        for k in order:
            q = qs[k]
            while idx[k] < len(q) and q[idx[k]] in seen:
                idx[k] += 1
            if idx[k] < len(q):
                n = q[idx[k]]
                idx[k] += 1
                seen.add(n)
                progressed = True
                yield n
        if not progressed:
            return


def run_officers(industries, limit):
    keys = [k.strip() for k in os.environ.get("CH_API_KEY", "").split(",") if k.strip()]
    if not keys:
        raise SystemExit("Set CH_API_KEY to your Companies House API key.")
    con = connect()
    lock = threading.Lock()
    work = queue.Queue(maxsize=200)
    stats = {"done": 0, "fit": 0, "t0": time.time()}

    def worker(key):
        client = ch_api.Client(key)
        wcon = connect()
        while True:
            n = work.get()
            if n is None:
                return
            nd, names, status = ch_api.fetch_officers(client, n)
            prof = None
            if nd in (1, 2):
                prof = ch_api.fetch_profile(client, n) + ch_api.fetch_owners(client, n)
            with lock:
                if nd is not None:
                    wcon.execute("INSERT OR REPLACE INTO officers VALUES (?,?,?,?,?)",
                                 (n, nd, names, status, ch_api.now()))
                if prof:
                    wcon.execute("INSERT OR REPLACE INTO profiles VALUES (?,?,?,?,?,?,?,?,?,?)",
                                 (n, *prof[:6], ch_api.now(), *prof[6:]))
                wcon.commit()
                stats["done"] += 1
                stats["fit"] += nd in (1, 2)
                if stats["done"] % 250 == 0:
                    rate = stats["done"] / (time.time() - stats["t0"]) * 3600
                    print(f"officers: {stats['done']} checked, {stats['fit']} with 1-2 directors "
                          f"({rate:.0f}/hr)", flush=True)

    threads = [threading.Thread(target=worker, args=(k,), daemon=True) for k in keys]
    for t in threads:
        t.start()
    for n in round_robin(pending_queues(con, industries, limit)):
        work.put(n)
    for _ in threads:
        work.put(None)
    for t in threads:
        t.join()
    print(f"officers: finished, {stats['done']} checked this run", flush=True)


def run_websites(follow, workers=24):
    con = connect()
    lock = threading.Lock()

    def one(row):
        n, name, pc = row
        try:
            res = websites.find_website(n, name, pc)
        except Exception:
            res = None
        res = res or {}
        with lock:
            con.execute("INSERT OR REPLACE INTO websites VALUES (?,?,?,?,?,?,?,?)",
                        (n, res.get("url"), res.get("match"), res.get("title"), res.get("description"),
                         res.get("phone"), res.get("email"), ch_api.now()))
            con.commit()
        return bool(res)

    total = found = 0
    with ThreadPoolExecutor(workers) as pool:
        while True:
            rows = con.execute(
                "SELECT c.number, c.name, c.postcode FROM companies c JOIN officers o USING(number) "
                "WHERE o.n_directors IN (1,2) AND c.number NOT IN (SELECT number FROM websites) "
                f"AND CAST(substr(c.incorporated,7,4) AS INTEGER) >= {MIN_INCORPORATION_YEAR} "
                "ORDER BY o.n_directors LIMIT 500").fetchall()
            if not rows:
                if not follow:
                    break
                time.sleep(60)
                continue
            for hit in pool.map(one, [tuple(r) for r in rows]):
                total += 1
                found += hit
            print(f"websites: {total} checked, {found} found", flush=True)


BATCH_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "batches")
STATE = os.path.join(BATCH_DIR, "state.sql.gz")
STATE_TABLES = ("officers", "profiles", "websites", "batched")


def run_batch():
    os.makedirs(BATCH_DIR, exist_ok=True)
    con = connect()
    n = (con.execute("SELECT max(batch) FROM batched").fetchone()[0] or 0) + 1
    path = os.path.join(BATCH_DIR, f"batch_{n:03d}_{datetime.date.today():%Y-%m-%d}.xlsx")
    path, rows = export.build(path, batch=n)
    new = con.execute("SELECT count(*) FROM batched WHERE batch=?", (n,)).fetchone()[0]
    if not new:
        os.remove(path)
        print("no new leads since last batch")
        return
    for r in rows:
        print(r)
    with gzip.open(STATE, "wt") as f:
        for t in STATE_TABLES:
            cols = [r[1] for r in con.execute(f"PRAGMA table_info({t})")]
            for row in con.execute(f"SELECT * FROM {t}"):
                vals = ",".join("NULL" if v is None else str(v) if isinstance(v, int)
                                else "'" + str(v).replace("'", "''") + "'" for v in row)
                f.write(f"INSERT INTO {t} ({','.join(cols)}) VALUES ({vals});\n")
    print(f"batch {n}: {new} new leads -> {path}")


def run_restore():
    con = connect()
    with gzip.open(STATE, "rt") as f:
        for line in f:
            con.execute(line.replace("INSERT INTO", "INSERT OR REPLACE INTO", 1))
    con.commit()
    print("restored", {t: con.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in STATE_TABLES})


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stage", choices=["bulk", "officers", "websites", "export", "batch", "restore"])
    ap.add_argument("--industries", help="comma-separated tab names (default: all)")
    ap.add_argument("--limit", type=int, help="max companies per industry this run")
    ap.add_argument("--follow", action="store_true", help="websites: keep polling for new leads")
    a = ap.parse_args()
    inds = [i.strip() for i in a.industries.split(",")] if a.industries else list(INDUSTRIES)
    if a.stage == "bulk":
        print("loaded", bulk.load(bulk.download()), "candidate companies")
    elif a.stage == "officers":
        run_officers(inds, a.limit)
    elif a.stage == "websites":
        run_websites(a.follow)
    elif a.stage == "batch":
        run_batch()
    elif a.stage == "restore":
        run_restore()
    else:
        path, rows = export.build()
        for r in rows:
            print(r)
        print("wrote", path)


if __name__ == "__main__":
    main()
