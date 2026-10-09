"""Rate-limited Companies House API client: officers + company profile."""
import datetime
import re
import threading
import time

import requests

API = "https://api.company-information.service.gov.uk"
# Limit is 600 requests / 5 min per key; stay a little under it.
MIN_INTERVAL = 300 / 580
DIRECTOR_ROLES = {"director", "corporate-director", "nominee-director", "corporate-nominee-director"}


class Client:
    def __init__(self, key):
        self.s = requests.Session()
        self.s.auth = (key, "")
        self._next = 0.0
        self._lock = threading.Lock()

    def get(self, path):
        for attempt in range(6):
            with self._lock:
                wait = self._next - time.monotonic()
                if wait > 0:
                    time.sleep(wait)
                self._next = time.monotonic() + MIN_INTERVAL
            try:
                r = self.s.get(API + path, timeout=30)
            except requests.RequestException:
                time.sleep(2 ** attempt)
                continue
            if r.status_code == 429:
                time.sleep(60)
                continue
            if r.status_code >= 500:
                time.sleep(2 ** attempt)
                continue
            if r.status_code == 401:
                raise SystemExit("Companies House rejected the API key (401).")
            return r
        return None


def now():
    return datetime.datetime.utcnow().isoformat(timespec="seconds")


def fetch_officers(client, number):
    """Returns (n_directors, names, status)."""
    r = client.get(f"/company/{number}/officers?items_per_page=100")
    if r is None:
        return None, "", "error"
    if r.status_code == 404:
        return 0, "", "not_found"
    data = r.json()
    names = [o.get("name", "").strip() for o in data.get("items", [])
             if o.get("officer_role") in DIRECTOR_ROLES and not o.get("resigned_on")]
    if data.get("total_results", 0) > 100 and len(names) <= 2:
        return 99, "", "too_many"  # unusual; not a small owner-led company
    return len(names), "; ".join(_tidy(n) for n in names), "ok"


def _tidy(name):
    name = re.sub(r"^(Mr|Mrs|Ms|Miss|Dr)\.?\s+", "", name.strip(), flags=re.I)
    # Companies House gives "SURNAME, Forename Middle"; show "Forename Middle Surname".
    if "," in name:
        last, first = name.split(",", 1)
        return f"{first.strip()} {last.strip().title()}"
    return name.title()


def fetch_profile(client, number):
    r = client.get(f"/company/{number}")
    if r is None or r.status_code != 200:
        return ("error", 0, 0, 0, 0, 0)
    d = r.json()
    return (
        d.get("company_status", ""),
        int(bool(d.get("undeliverable_registered_office_address"))),
        int(bool(d.get("registered_office_is_in_dispute"))),
        int(bool(d.get("has_insolvency_history"))),
        int(bool((d.get("accounts") or {}).get("overdue"))),
        int(bool((d.get("confirmation_statement") or {}).get("overdue"))),
    )


def fetch_owners(client, number):
    """Persons with significant control. Returns (owner_type, owner names).

    owner_type: 'individual' (owner-managed), 'corporate' (subsidiary of another
    company, so not owner-led), or 'unknown'.
    """
    r = client.get(f"/company/{number}/persons-with-significant-control")
    if r is None or r.status_code != 200:
        return "unknown", ""
    items = [i for i in r.json().get("items", []) if not i.get("ceased_on")]
    people = [_tidy(i.get("name", "")) for i in items if i.get("kind", "").startswith("individual")]
    corporate = [i for i in items if i.get("kind", "").startswith(("corporate", "legal-person"))]
    if people:
        return "individual", "; ".join(people)
    if corporate:
        return "corporate", "; ".join(i.get("name", "") for i in corporate)
    return "unknown", ""
