"""
UTIITSL PAN PSA Application Center scraper — human-in-the-loop CAPTCHA.

Scope (per approved plan): Rajasthan, searched district-by-district (34 districts).

How it works:
  1. Playwright opens a REAL, visible Chromium window and loads the search form.
  2. The script auto-selects "Search By District", the state (Rajasthan), and
     the current district from the on-site dropdowns (these are open, non-CAPTCHA
     AJAX endpoints — no automation touches the CAPTCHA at any point).
  3. The script then waits — not on a terminal prompt, but on the browser's own
     navigation event — for YOU to look at the browser window, read the CAPTCHA
     image, type it into the CAPTCHA box, and click Submit yourself. There is no
     terminal interaction required; this works even when stdin isn't a live TTY
     (e.g. run from an automated shell), because it only watches the browser.
  4. Once the page navigates (i.e. you clicked Submit and the results page
     loaded), the script scrapes the resulting HTML table (if any) and moves to
     the next district — reloading the page fresh so a new CAPTCHA/session
     token is issued, matching how the site behaves.

Nothing in this script reads, solves, guesses, or automates the CAPTCHA. If a
district's submission looks like it failed CAPTCHA validation, the script
automatically retries that district (fresh page, fresh CAPTCHA, up to
--max-attempts times) before giving up and moving on.
"""

import argparse
import csv
import json
import sys
import time
from pathlib import Path

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

BASE_URL = "https://psaonline.utiitsl.com/PanPSACenters/forms/applicationCenters"

STATE_IDS = {
    "ANDAMAN AND NICOBAR ISLANDS": "1", "ANDHRA PRADESH": "2", "ARUNACHAL PRADESH": "3",
    "ASSAM": "4", "BIHAR": "5", "CHANDIGARH": "6", "CHHATTISGARH": "33",
    "DADRA AND NAGAR HAVELI": "7", "DAMAN AND DIU": "8", "DELHI": "9", "GOA": "10",
    "GUJARAT": "11", "HARYANA": "12", "HIMACHAL PRADESH": "13", "JAMMU AND KASHMIR": "14",
    "JHARKHAND": "35", "KARNATAKA": "15", "KERALA": "16", "LADAKH": "37",
    "LAKSHADWEEP": "17", "MADHYA PRADESH": "18", "MAHARASHTRA": "19", "MANIPUR": "20",
    "MEGHALAYA": "21", "MIZORAM": "22", "NAGALAND": "23", "ODISHA": "24", "OTHER": "99",
    "PONDICHERRY": "25", "PUNJAB": "26", "RAJASTHAN": "27", "SIKKIM": "28",
    "TAMILNADU": "29", "TELANGANA": "36", "TRIPURA": "30", "UTTAR PRADESH": "31",
    "UTTARAKHAND": "34", "WEST BENGAL": "32",
}

RAJASTHAN_DISTRICTS = [
    "AJMER", "ALWAR", "BANSWARA", "BARAN", "BARMER", "BHARATPUR", "BHILWARA",
    "BIKANER", "BUNDI", "CHITTORGARH", "CHURU", "DAUSA", "DHOLPUR", "DUNGARPUR",
    "GANGANAGAR", "HANUMANGARH", "JAIPUR", "JAISALMER", "JALOR", "JHALAWAR",
    "JHUJHUNU", "JODHPUR", "KARAULI", "KOTA", "NAGAUR", "PALI", "PRATAPGARH",
    "RAJSAMAND", "SAWAI MADHOPUR", "SHIV GANJ", "SIKAR", "SIROHI", "TONK",
    "UDAIPUR",
]


def wait_for_district_options(page, timeout_ms=10000):
    page.wait_for_function(
        "document.querySelectorAll('#dist option').length > 1",
        timeout=timeout_ms,
    )


def select_district(page, district):
    """Some states' district option values have stray leading/trailing
    whitespace (e.g. " HYDERABAD ") since they come straight from the
    site's raw data. Match case/whitespace-insensitively instead of relying
    on Playwright's exact-value select_option, which would silently fail to
    find the option on those states."""
    return page.evaluate(
        """(district) => {
            const sel = document.getElementById('dist');
            const target = district.trim().toUpperCase();
            for (const opt of sel.options) {
                if (opt.value.trim().toUpperCase() === target) {
                    sel.value = opt.value;
                    sel.dispatchEvent(new Event('change'));
                    return true;
                }
            }
            return false;
        }""",
        district,
    )


def extract_results_table(html):
    """Generic scrape of the results DataTable (#example) if present."""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", id="example") or soup.find("table")
    if table is None:
        return None, []

    headers = [th.get_text(strip=True) for th in table.find_all("th")]
    rows = []
    body = table.find("tbody") or table
    for tr in body.find_all("tr"):
        cells = [td.get_text(strip=True) for td in tr.find_all("td")]
        if not cells:
            continue
        if headers and len(headers) == len(cells):
            rows.append(dict(zip(headers, cells)))
        else:
            rows.append({f"col_{i}": v for i, v in enumerate(cells)})
    return headers, rows


def page_has_results_table(html):
    """The pristine search form (and CAPTCHA-error reload of it) contains no
    <table> element at all — one only appears once a search actually
    succeeds. This is a much more reliable success signal than text-matching
    for words like "captcha"/"swal", which appear on every page regardless
    of outcome (the CAPTCHA field markup and SweetAlert2 <script> tag are
    always present, success or failure)."""
    soup = BeautifulSoup(html, "html.parser")
    return soup.find("table") is not None


def write_outputs(records, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    if not records:
        print("No records collected yet — skipping file export.")
        return

    json_path = out_dir / "pan_centers.json"
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)

    all_keys = []
    for r in records:
        for k in r.keys():
            if k not in all_keys:
                all_keys.append(k)
    csv_path = out_dir / "pan_centers.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=all_keys)
        writer.writeheader()
        writer.writerows(records)

    try:
        import pandas as pd

        xlsx_path = out_dir / "pan_centers.xlsx"
        pd.DataFrame(records).to_excel(xlsx_path, index=False)
    except ImportError:
        print("pandas/openpyxl not installed — skipping .xlsx export "
              "(csv and json were still written).")

    print(f"Wrote {len(records)} records to {json_path}, {csv_path}"
          f"{', ' + str(xlsx_path) if 'xlsx_path' in dir() else ''}")


def scrape_one_district(page, state_id, state_name, district, max_attempts, timeout_minutes):
    """Drive the form for one state/district search, waiting on YOU to solve
    each CAPTCHA in the visible browser window. Returns a list of row dicts
    (each tagged with _search_state/_search_district), or None if the
    district's dropdown value couldn't be found (bad name/whitespace)."""
    nav_timeout_ms = timeout_minutes * 60 * 1000

    for attempt in range(1, max_attempts + 1):
        page.goto(BASE_URL, wait_until="networkidle")

        page.check("#dist1")  # ensure "Search By District" is selected
        page.select_option("#state", value=state_id)
        wait_for_district_options(page)
        if not select_district(page, district):
            print(f"  WARNING: district '{district}' not found in the dropdown for "
                  f"{state_name} — check spelling/whitespace. Skipping.")
            return None
        page.focus("#captcha")  # cursor ready so you can type the CAPTCHA immediately

        print(
            f"  Attempt {attempt}/{max_attempts} — browser window is ready. "
            f"Please read the CAPTCHA, type it in, and click Submit "
            f"(you have up to {timeout_minutes} min)."
        )

        try:
            with page.expect_navigation(timeout=nav_timeout_ms):
                pass  # waits for the navigation YOU trigger by clicking Submit
        except PlaywrightTimeoutError:
            print(f"  Timed out waiting {timeout_minutes} min for submission. "
                  f"Skipping {district}.")
            return []

        try:
            page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass

        html = page.content()

        if not page_has_results_table(html):
            print("  No results table found — CAPTCHA was likely rejected. Retrying "
                  "this district with a fresh CAPTCHA." if attempt < max_attempts
                  else "  No results table again — giving up on this district.")
            continue

        # The results table is a jQuery DataTable with client-side pagination
        # (no `serverSide`/`ajax` option was used to init it) — it only keeps the
        # CURRENT page's rows in the live DOM, default page length 10. Force it to
        # show all rows via its own JS API before reading the DOM, otherwise we'd
        # silently only capture the first page.
        info_text = page.evaluate(
            """
            () => {
                if (!(window.jQuery && jQuery.fn.dataTable)) return null;
                const el = jQuery('#example');
                if (!el.length || !jQuery.fn.dataTable.isDataTable(el)) return null;
                const dt = el.DataTable();
                dt.page.len(-1).draw();
                return jQuery('.dataTables_info').text() || null;
            }
            """
        )
        if info_text:
            print(f"  DataTable info: {info_text}")
        page.wait_for_timeout(500)  # let the redraw settle

        html = page.content()
        headers, rows = extract_results_table(html)
        print(f"  Parsed {len(rows)} row(s) from results table.")

        for row in rows:
            row["_search_state"] = state_name
            row["_search_district"] = district
        return rows

    print(f"  Exhausted {max_attempts} attempts — moving on from {district}.")
    return []


def run(state_name: str, districts: list[str], out_dir: Path, headless: bool,
        max_attempts: int, timeout_minutes: int):
    if headless:
        print("WARNING: --headless was requested, but a human must see and "
              "solve the CAPTCHA in the browser window. Forcing headless=False.")
        headless = False

    state_id = STATE_IDS.get(state_name.upper())
    if state_id is None:
        print(f"Unknown state '{state_name}'. Known states: {list(STATE_IDS)}")
        sys.exit(1)

    records = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        for i, district in enumerate(districts, 1):
            print(f"\n[{i}/{len(districts)}] District: {district}")
            rows = scrape_one_district(page, state_id, state_name.upper(), district,
                                        max_attempts, timeout_minutes)
            if rows:
                records.extend(rows)
                write_outputs(records, out_dir)  # incremental save after each district
            time.sleep(1)  # be polite between requests

        browser.close()

    write_outputs(records, out_dir)
    print(f"\nDone. {len(records)} total record(s) collected across "
          f"{len(districts)} district(s) in {state_name.upper()}.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", default="RAJASTHAN", help="State to search (default: RAJASTHAN)")
    parser.add_argument(
        "--districts",
        default=",".join(RAJASTHAN_DISTRICTS),
        help="Comma-separated list of districts to search (default: all 34 Rajasthan districts)",
    )
    parser.add_argument("--out-dir", default="output", help="Output directory for CSV/XLSX/JSON")
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Ignored — a human must be present to solve the CAPTCHA; kept for CLI compatibility.",
    )
    parser.add_argument(
        "--max-attempts", type=int, default=5,
        help="Max retries per district if the CAPTCHA looks rejected (default: 5)",
    )
    parser.add_argument(
        "--timeout-minutes", type=int, default=10,
        help="How long to wait per attempt for you to solve the CAPTCHA and submit (default: 10)",
    )
    args = parser.parse_args()

    districts = [d.strip().upper() for d in args.districts.split(",") if d.strip()]
    run(args.state, districts, Path(args.out_dir), args.headless,
        args.max_attempts, args.timeout_minutes)


if __name__ == "__main__":
    main()
