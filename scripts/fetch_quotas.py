#!/usr/bin/env python3
"""
Barrett Steel — UK Steel Quota Tracker data fetcher.

Pulls live quota balance data from the UK Government's Trade Tariff API
(trade-tariff.service.gov.uk) for every steel safeguard / trade measure
quota order number, works out usage %, status, and a predicted exhaustion
date, and writes the result to quota-data.json.

This script needs NO API key — the Trade Tariff quotas/search endpoint is
public. Run it daily via the included GitHub Actions workflow.

Docs: https://api.trade-tariff.service.gov.uk/reference.html
"""

import json
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

API_BASE = "https://www.trade-tariff.service.gov.uk/uk/api/quotas/search"
HEADERS = {"Accept": "application/vnd.hmrc.2.0+json", "User-Agent": "BarrettSteelQuotaTracker/1.0"}

OUTPUT_FILE = Path(__file__).parent.parent / "quota-data.json"
PREVIOUS_FILE = Path(__file__).parent.parent / "quota-data.json"  # read before overwrite

# Status thresholds — adjust here if Barrett Steel wants different bands.
WATCH_THRESHOLD = 70.0     # % used
CRITICAL_THRESHOLD = 90.0  # % used

# Steel safeguard / trade measure quota order numbers, grouped by official
# category. These are public HMRC/DBT quota order numbers (factual
# regulatory identifiers, not creative content) covering the steel
# safeguard measure categories currently in force.
#
# related_product / related_product_url map each category to the real
# Barrett Steel product page, confirmed against barrettsteel.com's live
# navigation. Categories with no confirmed dedicated page (Rebar, Wire Rod,
# Stainless Wire Rod, Non-Alloy Wire, Railway Material) use None — these
# simply show no product link rather than guessing at a URL. If one of
# these does have a real page that didn't surface in the nav crawl, add it
# here.
CATEGORIES = [
    ("CAT 1", "Non-alloy & other alloy hot-rolled sheets & strips", ["058600", "058601", "058602", "058603"], "Steel Sheets and Plates", "/products/general-steels/sheet-and-plate/"),
    ("CAT 4", "Metallic coated sheets", ["058604", "058605", "058606", "058607", "058608"], "Steel Sheets and Plates", "/products/general-steels/sheet-and-plate/"),
    ("CAT 5", "Organic coated sheets", ["058609", "058610", "058611"], "Steel Sheets and Plates", "/products/general-steels/sheet-and-plate/"),
    ("CAT 6", "Tin mill products", ["058612", "058613", "058614", "058615"], "Steel Sheets and Plates", "/products/general-steels/sheet-and-plate/"),
    ("CAT 7", "Non-alloy & other alloy quarto plates", ["058616", "058617", "058618", "058619"], "Steel Sheets and Plates", "/products/general-steels/sheet-and-plate/"),
    ("CAT 12A", "Alloy merchant bars & light sections", ["058620", "058621"], "Carbon and Alloy Steel", "/products/engineering/carbon-and-alloy-steel/"),
    ("CAT 12B", "Non-alloy merchant bars & light sections", ["058622", "058623", "058624"], "Merchant Bar Steel", "/products/general-steels/merchant-bar/"),
    ("CAT 13", "Rebars", ["058625", "058626", "058627"], None, None),
    ("CAT 14", "Stainless bars & light sections", ["058628", "058629", "058630"], "Stainless, Duplex & Super Duplex", "/products/international/stainless,-duplex-super-duplex/"),
    ("CAT 15", "Stainless wire rod", ["058631", "058632", "058633"], None, None),
    ("CAT 16", "Non-alloy & other alloy wire rod", ["058634", "058635"], None, None),
    ("CAT 17", "Angles, shapes & sections", ["058636", "058637", "058638", "058639"], "Mild Steel Angles", "/products/general-steels/mild-steel-angles/"),
    ("CAT 19", "Railway material", ["058640", "058641"], None, None),
    ("CAT 20", "Gas pipes", ["058642", "058643", "058644", "058645"], "Nominal Bore Tube", "/products/tubes/nominal-bore-tube/"),
    ("CAT 21", "Hollow sections", ["058646", "058647", "058648"], "Hollow Sections", "/products/general-steels/hollow-sections/"),
    ("CAT 25A", "Large welded tubes (1)", ["058649", "058650", "058651", "058652", "058653"], "Offshore & Marine Grades", "/products/tubes/offshore-marine-grades/"),
    ("CAT 25B", "Large welded tubes (2)", ["058654", "058655", "058656", "058657", "058658"], "Offshore & Marine Grades", "/products/tubes/offshore-marine-grades/"),
    ("CAT 26", "Other welded tubes", ["058659", "058660", "058661", "058662", "058663", "058664"], "ERW Precision Tube", "/products/tubes/erw-precision-tube/"),
    ("CAT 27", "Non-alloy & other alloy cold finished bars", ["058665", "058666", "058667"], "Carbon and Alloy Steel", "/products/engineering/carbon-and-alloy-steel/"),
    ("CAT 28", "Non-alloy wire", ["058668", "058669", "058670", "058671"], None, None),
]


def fetch_order_number(order_number, retries=3):
    """Call the Trade Tariff API for a single quota order number."""
    url = f"{API_BASE}?order_number={order_number}"
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            print(f"  HTTP {e.code} for order_number={order_number} (attempt {attempt+1})")
            if e.code in (401, 403):
                print("  -> Auth error: the public endpoint may now require a free API key.")
                print("     Check https://hub.trade-tariff.service.gov.uk/ to register one,")
                print("     then add it as an Authorization header above.")
                return None
        except Exception as e:
            print(f"  Error fetching {order_number} (attempt {attempt+1}): {e}")
        time.sleep(2)
    return None


def pick_current_definition(definitions):
    """Pick the definition (quota period) that covers today, else the most
    recent one that has already started."""
    now = datetime.now(timezone.utc)
    current, most_recent = None, None
    for d in definitions:
        attrs = d.get("attributes", {})
        start = attrs.get("validity_start_date")
        end = attrs.get("validity_end_date")
        if not start:
            continue
        start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(end.replace("Z", "+00:00")) if end else None
        if start_dt <= now and (end_dt is None or now <= end_dt):
            current = d
            break
        if start_dt <= now and (most_recent is None or start_dt > datetime.fromisoformat(
                most_recent["attributes"]["validity_start_date"].replace("Z", "+00:00"))):
            most_recent = d
    return current or most_recent


def find_origin(order_number, payload):
    """Look up the geographical area (origin) linked to this order number
    from the 'included' section of the JSON:API response."""
    included = payload.get("included", [])
    for item in included:
        if item.get("type") == "geographical_area":
            desc = item.get("attributes", {}).get("description")
            if desc:
                return desc
    return "Unknown"


def compute_status(pct_used, balance):
    if balance <= 0:
        return "EXHAUSTED"
    if pct_used >= CRITICAL_THRESHOLD:
        return "CRITICAL"
    if pct_used >= WATCH_THRESHOLD:
        return "WATCH"
    return "OPEN"


def predict_exhaustion(start_date, balance, used, now):
    """Simple average-usage-rate projection, matching the disclaimed
    'estimate only' methodology used across the industry for this kind of
    tracker."""
    if balance <= 0:
        return "Already exhausted"
    if used <= 0:
        return "Not on course to exhaust"
    days_elapsed = max((now - start_date).days, 1)
    daily_rate = used / days_elapsed
    if daily_rate <= 0:
        return "Not on course to exhaust"
    days_remaining = balance / daily_rate
    if days_remaining > 120:  # beyond ~4 months, treat as not on course
        return "Not on course to exhaust"
    exhaustion_date = now + __import__("datetime").timedelta(days=days_remaining)
    return exhaustion_date.strftime("%d %b %Y")


def process_order_number(order_number):
    payload = fetch_order_number(order_number)
    if not payload or not payload.get("data"):
        return None

    definitions = payload["data"]
    definition = pick_current_definition(definitions)
    if not definition:
        return None

    attrs = definition["attributes"]
    initial_volume = float(attrs.get("initial_volume", 0) or 0)
    balance = float(attrs.get("balance", 0) or 0)
    used = initial_volume - balance
    pct_used = round((used / initial_volume) * 100, 1) if initial_volume else 0.0
    last_allocation = attrs.get("last_allocation_date")
    start = attrs.get("validity_start_date")
    start_dt = datetime.fromisoformat(start.replace("Z", "+00:00")) if start else datetime.now(timezone.utc)
    now = datetime.now(timezone.utc)

    return {
        "order_number": order_number,
        "origin": find_origin(order_number, payload),
        "initial_volume": initial_volume,
        "balance": balance,
        "pct_used": pct_used,
        "last_allocation_date": (
            datetime.fromisoformat(last_allocation.replace("Z", "+00:00")).strftime("%d %b %Y")
            if last_allocation else "No allocations yet"
        ),
        "predicted_exhaustion": predict_exhaustion(start_dt, balance, used, now),
        "status": compute_status(pct_used, balance),
    }


def main():
    print(f"Fetching UK Steel Quota data — {datetime.now(timezone.utc).isoformat()}")

    # Load previous snapshot (if any) to detect status changes for alerts.
    previous = {}
    if PREVIOUS_FILE.exists():
        try:
            old = json.loads(PREVIOUS_FILE.read_text())
            for cat in old.get("categories", []):
                for q in cat.get("quotas", []):
                    previous[q["order_number"]] = q["status"]
        except Exception:
            pass

    result_categories = []
    changes = []  # quotas that newly crossed into WATCH/CRITICAL today

    for cat_code, cat_name, order_numbers, related_product, related_product_url in CATEGORIES:
        quotas = []
        for order_number in order_numbers:
            print(f"  {cat_code} / {order_number}...")
            record = process_order_number(order_number)
            if record:
                quotas.append(record)
                prev_status = previous.get(order_number)
                if record["status"] in ("WATCH", "CRITICAL") and prev_status not in ("WATCH", "CRITICAL"):
                    changes.append({
                        "order_number": order_number,
                        "category": f"{cat_code}: {cat_name}",
                        "new_status": record["status"],
                    })
            time.sleep(0.3)  # be a polite API citizen
        if quotas:
            result_categories.append({
                "code": cat_code,
                "name": cat_name,
                "related_product": related_product,
                "related_product_url": related_product_url,
                "quotas": quotas,
            })

    output = {
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "source": "UK Government Trade Tariff API (trade-tariff.service.gov.uk), Open Government Licence v3.0",
        "categories": result_categories,
    }

    OUTPUT_FILE.write_text(json.dumps(output, indent=2))
    print(f"Wrote {OUTPUT_FILE}")

    changes_file = Path(__file__).parent.parent / "quota-changes.json"
    changes_file.write_text(json.dumps({"generated": datetime.now(timezone.utc).isoformat(), "changes": changes}, indent=2))
    print(f"Wrote {changes_file} ({len(changes)} new WATCH/CRITICAL crossings)")


if __name__ == "__main__":
    main()
