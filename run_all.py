"""
Fully automatic national run: walks every state/district pair that isn't
already in output/pan_centers.json, skipping anything already completed,
and writes + updates progress_tracker.xlsx after every single district. No
manual --state/--districts entry needed.

You still solve every CAPTCHA yourself in the visible browser window — the
only thing automated here is the bookkeeping (which state/district is next,
what's already done, saving/tracking results).

Usage:
    python run_all.py                      # every remaining district nationally
    python run_all.py --state MAHARASHTRA   # only remaining districts in one state
    python run_all.py --limit 20            # stop after 20 districts this run
    python run_all.py --max-attempts 5 --timeout-minutes 10   # (these are the defaults)

Safe to stop anytime (Ctrl+C or close the browser) — progress is saved after
every district, so re-running picks up exactly where you left off.
"""

import argparse
import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

import scraper as S
import merge_and_track as MT


def get_completed_keys():
    if MT.OUTPUT_DIR.joinpath("pan_centers.json").exists():
        with MT.OUTPUT_DIR.joinpath("pan_centers.json").open(encoding="utf-8") as f:
            records = json.load(f)
    else:
        records = []
    completed = {(r["_search_state"], r["_search_district"]) for r in records}
    return records, completed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", default=None,
                         help="Restrict to one state's remaining districts (default: all states)")
    parser.add_argument("--limit", type=int, default=None,
                         help="Stop after this many districts in this run (default: no limit)")
    parser.add_argument("--max-attempts", type=int, default=5,
                         help="Max CAPTCHA retries per district (default: 5)")
    parser.add_argument("--timeout-minutes", type=int, default=10,
                         help="Max wait per attempt for you to solve the CAPTCHA (default: 10)")
    args = parser.parse_args()

    all_districts = MT.load_all_states_districts()
    records, completed = get_completed_keys()

    remaining = [d for d in all_districts if (d["state"], d["district"]) not in completed]
    if args.state:
        remaining = [d for d in remaining if d["state"] == args.state.upper()]
        if not remaining:
            print(f"Nothing remaining for state '{args.state.upper()}' "
                  f"(either fully complete already, or not a recognized state).")
            return
    if args.limit:
        remaining = remaining[: args.limit]

    print(f"{len(remaining)} district(s) queued this run "
          f"({len(completed)} already completed nationally out of {len(all_districts)}).")
    if not remaining:
        print("Nothing to do.")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        for i, d in enumerate(remaining, 1):
            state_name, district = d["state"], d["district"]
            state_id = S.STATE_IDS[state_name]
            print(f"\n[{i}/{len(remaining)}] {state_name} / {district}")

            rows = S.scrape_one_district(page, state_id, state_name, district,
                                          args.max_attempts, args.timeout_minutes)

            if rows is None:
                # Bad dropdown match — still record it as "attempted" so it doesn't
                # loop forever; scrape_one_district already printed the warning.
                pass
            elif rows:
                records.extend(rows)

            # Save + update the tracker after every district, success or not,
            # so progress is never lost and the tracker always reflects reality.
            MT.write_dataset(records, MT.OUTPUT_DIR)
            MT.rebuild_tracker(records)

            time.sleep(1)  # be polite between requests

        browser.close()

    print(f"\nRun finished. output/ now has {len(records)} total records.")


if __name__ == "__main__":
    main()
