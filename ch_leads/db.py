"""SQLite store shared by all stages, so runs can stop and resume."""
import os
import sqlite3

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
DB_PATH = os.path.join(DATA_DIR, "leads.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS companies (
    number TEXT PRIMARY KEY, name TEXT, address TEXT, town TEXT, postcode TEXT,
    incorporated TEXT, account_category TEXT, sic TEXT, industries TEXT,
    accounts_due TEXT, confstmt_due TEXT
);
CREATE TABLE IF NOT EXISTS officers (
    number TEXT PRIMARY KEY, n_directors INTEGER, names TEXT, status TEXT, fetched_at TEXT
);
CREATE TABLE IF NOT EXISTS profiles (
    number TEXT PRIMARY KEY, status TEXT, undeliverable INTEGER, in_dispute INTEGER,
    insolvency INTEGER, accounts_overdue INTEGER, confstmt_overdue INTEGER, fetched_at TEXT,
    owner_type TEXT, owners TEXT
);
CREATE TABLE IF NOT EXISTS websites (
    number TEXT PRIMARY KEY, url TEXT, match TEXT, title TEXT, description TEXT,
    phone TEXT, email TEXT, checked_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_officers_n ON officers(n_directors);
"""


def connect():
    os.makedirs(DATA_DIR, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=60, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.executescript(SCHEMA)
    cols = {r[1] for r in con.execute("PRAGMA table_info(profiles)")}
    for c in ("owner_type", "owners"):
        if c not in cols:
            con.execute(f"ALTER TABLE profiles ADD COLUMN {c} TEXT")
    return con
