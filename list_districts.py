"""
Fetch the district list for a state from UTIITSL's open, unauthenticated
JSON endpoint (no CAPTCHA involved) and print a ready-to-paste --districts
value for scraper.py.

Usage:
    python list_districts.py --state "MAHARASHTRA"
"""

import argparse
import sys
import urllib.request
import json

from scraper import STATE_IDS

BASE = "https://psaonline.utiitsl.com/PanPSACenters/forms/loadDistByStateId/"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", required=True, help="State name, e.g. MAHARASHTRA")
    args = parser.parse_args()

    state_id = STATE_IDS.get(args.state.upper())
    if state_id is None:
        print(f"Unknown state '{args.state}'.")
        print("Known states:", ", ".join(sorted(STATE_IDS)))
        sys.exit(1)

    req = urllib.request.Request(BASE + state_id, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    districts = [d["distName"].strip() for d in data]
    # De-dupe while preserving order (some states list the same district
    # name twice with tiny formatting differences that both trim to the same string).
    seen = set()
    unique = []
    for d in districts:
        if d not in seen:
            seen.add(d)
            unique.append(d)

    print(f"{args.state.upper()} — {len(unique)} unique district(s) "
          f"({len(districts)} raw entries returned by the API)\n")
    for d in unique:
        print(f"  {d}")

    print("\nReady to paste into scraper.py:\n")
    print(f'python scraper.py --state "{args.state.upper()}" --districts "{",".join(unique)}" '
          f'--out-dir output_{args.state.lower().replace(" ", "_")}')


if __name__ == "__main__":
    main()
