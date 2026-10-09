# Bill Pay lead builder (Companies House)

Builds an Excel workbook of active UK companies with **1–2 directors** in the Bill Pay
target industries. It has one tab per industry, plus a Summary tab.

## Pipeline
1. `python3 run.py bulk`: downloads the free Companies House bulk file and keeps active
   private and public limited companies whose SIC codes match `industries.py`. Dormant
   companies and those with no accounts filed are dropped. About 330k candidates.
2. `CH_API_KEY=... python3 run.py officers`: counts current directors for each candidate
   through the Companies House API. For companies with 1–2 directors it also pulls the
   profile: insolvency history, undeliverable or disputed registered office, overdue filings.
   Companies are processed round-robin across industries, larger filers first. The run is
   rate-limited to the 600 requests / 5 min API limit, and it is resumable. Several keys
   can be passed comma-separated to run faster.
3. `python3 run.py websites --follow`: guesses domains from the company name and keeps a
   site only when it names the company. **Confirmed** means the company number (or the
   name plus postcode) is on the site. **Probable** means only the name matches. It also
   scrapes the meta description, phone and email.
4. `python3 run.py export`: writes `output/bill_pay_leads_<date>.xlsx`.

Stages 2 and 3 can run at the same time. All state is kept in `data/leads.db`, which is
gitignored. Never commit the API key.
