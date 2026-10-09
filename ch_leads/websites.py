"""Find and verify company websites by guessing domains from the company name."""
import html as htmlmod
import os
import re
from urllib.parse import unquote, urljoin

import requests

UA = {"User-Agent": "Mozilla/5.0 (compatible; lead-research/1.0)"}
SUFFIXES = r"\b(LIMITED|LTD|PLC|L\.T\.D|CO|COMPANY|\(UK\)|UK|U\.K|GB|GROUP|HOLDINGS|THE|SERVICES|SERVICE|AND)\b"
SKIP_HOSTS = ("facebook.", "linkedin.", "sedo", "godaddy", "parking", "hugedomains", "dan.com", "afternic")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?:\+44\s?\(?0?\)?\s?|\b0)(?:\d[\s-]?){9,10}\b")
EXTRA_PAGES = ("contact", "contact-us", "about", "about-us", "privacy-policy", "terms")


def _words(name):
    n = name.upper().replace("&", " AND ").replace("'", "")
    full = re.sub(r"[^A-Z0-9 ]", " ", n).split()
    core = re.sub(r"[^A-Z0-9 ]", " ", re.sub(SUFFIXES, " ", n)).split()
    return [w.lower() for w in full], [w.lower() for w in core]


def candidate_domains(name):
    full, core = _words(name)
    if not core:
        return []
    joined, hyph = "".join(core), "-".join(core)
    out = [f"{joined}.co.uk", f"{joined}.com", f"{joined}.uk", f"{hyph}.co.uk", f"{hyph}.com",
           f"{joined}ltd.co.uk", f"{joined}uk.co.uk", f"{joined}.net"]
    fj = "".join(w for w in full if w not in ("limited", "ltd", "plc"))
    if fj != joined:
        out += [f"{fj}.co.uk", f"{fj}.com"]
    seen, res = set(), []
    for d in out:
        if d not in seen and len(d.split(".")[0]) >= 3:
            seen.add(d)
            res.append(d)
    return res


def _fetch(url, timeout=8):
    try:
        r = requests.get(url, headers=UA, timeout=timeout, allow_redirects=True)
        if r.status_code >= 400 or "html" not in r.headers.get("content-type", ""):
            return None
        if any(s in r.url for s in SKIP_HOSTS):
            return None
        return r
    except requests.RequestException:
        return None


def _text(html):
    t = re.sub(r"(?is)<(script|style).*?</\1>", " ", html)
    t = htmlmod.unescape(re.sub(r"(?s)<[^>]+>", " ", t))
    return re.sub(r"\s+", " ", t)


def _meta(html):
    m = None
    for tag in re.findall(r"(?is)<meta\b[^>]*>", html):
        if re.search(r"""(?i)(name|property)\s*=\s*["'](og:)?description["']""", tag):
            c = re.search(r"""(?is)content\s*=\s*(["'])(.*?)\1""", tag)
            if c:
                m = c.group(2)
                break
    t = re.search(r"(?is)<title[^>]*>(.*?)</title>", html)
    clean = lambda s: re.sub(r"\s+", " ", htmlmod.unescape(s)).strip()[:300]
    return (clean(t.group(1)) if t else ""), (clean(m) if m else "")


def _number_on_page(number, text):
    n = number.lstrip("0")
    pat = r"(?<!\d)0*" + r"\s?".join(n) + r"(?!\d)"
    return re.search(pat, text) is not None and len(n) >= 5


def _contacts(html, text):
    emails = [e for e in re.findall(r'mailto:([^"\'?>\s]+)', html)] + EMAIL_RE.findall(text)
    emails = [e for e in emails if not re.search(r"\.(png|jpg|jpeg|gif|svg|webp)$", e, re.I)
              and "example" not in e and "sentry" not in e and "wixpress" not in e]
    phones = re.findall(r'tel:([+\d\s()-]{9,})', html) + PHONE_RE.findall(text)
    email = unquote(emails[0]).strip() if emails else ""
    return (phones[0].strip() if phones else ""), email


DIRECTORY_HOSTS = (
    "companieshouse", "company-information.service.gov.uk", "endole", "opencorporates", "linkedin.",
    "facebook.", "instagram.", "twitter.", "x.com", "yell.com", "companycheck", "bizdb", "dnb.com",
    "zoominfo", "checkcompany", "companiesintheuk", "find-and-update", "thegazette", "yelp.",
    "trustpilot", "glassdoor", "indeed.", "cylex", "192.com", "scoot.co.uk", "thomsonlocal",
    "freeindex", "companydatashop", "suite.endole", "bloomberg", "crunchbase", "wikipedia",
    "youtube", "tiktok", "pinterest", "amazon.", "ebay.", "google.", "bing.", "apple.com",
)


def search_urls(name, town):
    """Top organic Google results via Serper.dev (needs SERPER_API_KEY)."""
    key = os.environ.get("SERPER_API_KEY")
    if not key:
        return []
    q = re.sub(r"\b(LIMITED|LTD|PLC)\b\.?", "", name, flags=re.I).strip()
    try:
        r = requests.post("https://google.serper.dev/search", timeout=15,
                          headers={"X-API-KEY": key, "Content-Type": "application/json"},
                          json={"q": f"{q} {town or ''}".strip(), "gl": "uk", "num": 10})
        items = r.json().get("organic", []) if r.status_code == 200 else []
    except (requests.RequestException, ValueError):
        return []
    urls = []
    for it in items:
        link = it.get("link", "")
        host = re.sub(r"^https?://", "", link).split("/")[0].lower()
        if link and not any(d in host for d in DIRECTORY_HOSTS):
            root = "https://" + host
            if root not in urls:
                urls.append(root)
    return urls[:5]


def find_website(number, name, postcode, town=None):
    """Returns dict(url, match, title, description, phone, email) or None.

    Guesses domains from the name first (free); if none is confirmed, falls
    back to a Google search via Serper when SERPER_API_KEY is set.
    """
    full, core = _words(name)
    core_phrase = " ".join(core)
    pc = (postcode or "").upper().replace(" ", "")
    probable = None
    guesses = [f"https://{d}" for d in candidate_domains(name)]
    searched = False
    queue = list(guesses)
    while queue or not searched:
        if not queue:
            searched = True
            queue = [u for u in search_urls(name, town) if u not in guesses]
            continue
        url = queue.pop(0)
        r = _fetch(url) or (_fetch(url.replace("https://", "http://")) if url in guesses else None)
        if r is None:
            continue
        html = r.text[:600000]
        text = _text(html)
        title, desc = _meta(html)
        pages = [(html, text)]
        confirmed = _number_on_page(number, text)
        if not confirmed:
            for p in EXTRA_PAGES:
                rp = _fetch(urljoin(r.url, "/" + p), timeout=6)
                if rp is None:
                    continue
                t2 = _text(rp.text[:600000])
                pages.append((rp.text, t2))
                if _number_on_page(number, t2):
                    confirmed = True
                    break
        alltext = " ".join(t for _, t in pages)
        upper = alltext.upper()
        name_hit = len(core_phrase) >= 4 and core_phrase.upper() in re.sub(r"[^A-Z0-9 ]", " ", upper)
        if not confirmed and name_hit and pc and pc in upper.replace(" ", ""):
            confirmed = True
        phone, email = "", ""
        for h, t in pages:
            ph, em = _contacts(h, t)
            phone, email = phone or ph, email or em
        rec = dict(url=r.url.rstrip("/"), title=title, description=desc, phone=phone, email=email)
        if confirmed:
            return dict(rec, match="Confirmed")
        # Name alone can match a different business (e.g. a brand); also need
        # the registered name with Ltd/Limited, or the registered town/postcode area.
        reg_name = re.sub(r"[^A-Z0-9 ]", " ", " ".join(full).upper())
        local = (town and town.upper() in upper) or (pc and pc[:-3] and re.search(
            r"\b" + re.escape(pc[:-3]) + r"\s?\d[A-Z]{2}\b", upper))
        if probable is None and name_hit and (reg_name in re.sub(r"[^A-Z0-9 ]", " ", upper) or local):
            probable = dict(rec, match="Probable")
    return probable
