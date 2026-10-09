"""Target industries for Bill Pay leads: SIC code map and fit-text templates.

Edit this file to add or change industries. Codes are 5-digit UK SIC 2007.
"""


def _r(a, b):
    return {str(c) for c in range(a, b + 1)}


# Ordered: specific industries first. Manufacturing is computed as "any
# section C code not claimed by a more specific tab".
INDUSTRIES = {
    "Car Sales & Auctions": {
        "sic": {"45111", "45112", "45190", "45310"},
        "angle": "Buys stock at auction and from trade sellers, who are paid by bank transfer, often for £10k+ per vehicle",
    },
    "Pharmaceuticals": {
        "sic": {"21100", "21200", "46460", "47730"},
        "angle": "Pays wholesalers and manufacturers by bank transfer on recurring high-value stock invoices",
    },
    "Civils - Heavy Tarmac": {
        "sic": {"42110", "42120", "42130", "42910", "42990", "43120", "23990"},
        "angle": "Pays quarries, asphalt plants and plant-hire firms by bank transfer, often on large monthly accounts",
    },
    "Builders Merchants": {
        "sic": {"46730", "46740", "47520"},
        "angle": "Pays timber, aggregate and building-products suppliers by bank transfer on large trade invoices",
    },
    "IT Hardware": {
        "sic": {"26110", "26120", "26200", "46510", "46520", "47410", "95110"},
        "angle": "Pays distributors (e.g. Ingram, TD Synnex, Westcoast) and OEMs by bank transfer for hardware stock",
    },
    "Workwear & Textiles": {
        "sic": {"14120", "14190", "46410", "46420"} | _r(13100, 13990),
        "angle": "Pays fabric mills, garment makers and overseas manufacturers by bank transfer for bulk orders",
    },
    "Food Wholesale": {
        "sic": {"46170"} | _r(46310, 46390),
        "angle": "Pays growers, producers and importers by bank transfer on frequent, high-volume stock invoices",
    },
    "Wholesale General": {
        "sic": {"46180", "46190", "46499", "46690", "46760", "46900"},
        "angle": "Buys stock from manufacturers and importers who invoice for bank transfer, not card",
    },
    "Packaging": {
        "sic": {"16240", "17211", "17219", "22220", "25920", "82920"},
        "angle": "Pays board mills, resin and film suppliers by bank transfer for raw materials",
    },
    "Engineering": {
        "sic": {"71121", "71122", "71129", "25110", "25620"} | _r(28110, 28990) | _r(33110, 33200),
        "angle": "Pays steel stockholders, machining subcontractors and component suppliers by bank transfer",
    },
    "Manufacturing": {
        "sic": None,  # filled below
        "angle": "Pays raw-material and component suppliers by bank transfer on regular high-value invoices",
    },
}

_claimed = set().union(*(v["sic"] for v in INDUSTRIES.values() if v["sic"]))
# Section C = divisions 10-33.
INDUSTRIES["Manufacturing"]["sic"] = {
    str(c) for c in range(10000, 34000) if str(c) not in _claimed
}

SIC_TO_INDUSTRIES = {}
for _name, _v in INDUSTRIES.items():
    for _c in _v["sic"]:
        SIC_TO_INDUSTRIES.setdefault(_c, []).append(_name)

# Only companies incorporated in or after this year (older ones skew old-school).
MIN_INCORPORATION_YEAR = 1990

BILL_PAY_LINE = (
    "Bill Pay lets them pay these non-card suppliers from Capital on Tap: the 1.5% fee is a "
    "deductible business cost while they earn 1% (credit) / 1.25% (preload) cashback."
)


def director_line(n):
    if n == 1:
        return ("Sole director, so the owner makes the payment decisions and personally keeps "
                "the rewards. Ideal fit.")
    return ("Two directors: a small owner-led board, quick to decide, and the rewards go "
            "straight to the decision-makers.")


def fit_text(industry, n_directors):
    return f"{INDUSTRIES[industry]['angle']}. {BILL_PAY_LINE} {director_line(n_directors)}"
