"""Bill Pay lead builder.

Stages (each resumable, all state in data/leads.db):
  python3 run.py bulk        # download + load Companies House bulk data
  python3 run.py officers    # director counts + profile checks via API (needs CH_API_KEY)
  python3 run.py websites    # find + verify websites for 1-2 director companies
  python3 run.py export      # write output/bill_pay_leads_<date>.xlsx

CH_API_KEY may hold several comma-separated keys to multiply throughput.
"""
import argparse
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
from industries import INDUSTRIES

# Prefer companies filing fuller accounts (bigger turnover) and with a trading history.
ACCOUNT_RANK = """CASE account_category
  WHEN 'FULL' THEN 0 WHEN 'MEDIUM' THEN 0 WHEN 'GROUP' THEN 0 WHEN 'SMALL' THEN 1
  WHEN 'TOTAL EXEMPTION FULL' THEN 2 WHEN 'AUDIT EXEMPTION SUBSIDIARY' THEN 3
  WHEN 'UNAUDITED ABRIDGED' THEN 3 WHEN 'TOTAL EXEMPTION SMALL' THEN 3
  WHEN 'MICRO ENTITY' THEN 4 ELSE 5 END"""


def pending_queues(con, industries, limit):
    qs = {}
    for ind in industries:
        sql = (f"SELECT number FROM companies WHERE ('|'||industries||'|') LIKE ? "
               f"AND number NOT IN (SELECT number FROM officers) "
               f"ORDER BY {ACCOUNT_RANK}, substr(incorporated,7,4)||substr(incorporated,4,2)")
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
            prof = ch_api.fetch_profile(client, n) if nd in (1, 2) else None
            with lock:
                if nd is not None:
                    wcon.execute("INSERT OR REPLACE INTO officers VALUES (?,?,?,?,?)",
                                 (n, nd, names, status, ch_api.now()))
                if prof:
                    wcon.execute("INSERT OR REPLACE INTO profiles VALUES (?,?,?,?,?,?,?,?)",
                                 (n, *prof, ch_api.now()))
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


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stage", choices=["bulk", "officers", "websites", "export"])
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
    else:
        path, rows = export.build()
        for r in rows:
            print(r)
        print("wrote", path)


if __name__ == "__main__":
    main()
