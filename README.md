# UTIITSL PAN PSA Center Scraper

Extracts PAN Application Center records from `psaonline.utiitsl.com`
nationally. See `recon_report.md` and `captcha_analysis.md` for the
technical investigation this is built on.

Four scripts work together:

| Script | What it does |
|---|---|
| `run_all.py` | **Main tool.** Automatically walks every state/district not yet in `output/`, skipping completed ones, saving + updating the tracker after every district. No manual state/district entry. |
| `scraper.py` | Lower-level driver `run_all.py` builds on — targets one state/district list you specify by hand. Still useful for one-off/ad-hoc runs. |
| `list_districts.py` | Looks up a state's district list (no CAPTCHA — open API). Mostly superseded by `run_all.py`, but handy for inspecting a state before running it. |
| `merge_and_track.py` | Merges a `scraper.py` run's output folder into `output/` and rebuilds `progress_tracker.xlsx`. Not needed if you use `run_all.py`, which does this itself after every district. |

## How it works (human-in-the-loop CAPTCHA)

The site's search results endpoint is protected by a CAPTCHA and sits behind
bot-mitigation (F5/Shape-style). Per this project's ground rules, the
CAPTCHA is **never** automated, solved via OCR/vision models, or sent to a
solving service — by this code or by you plugging in your own solver script.
That rule is non-negotiable for this project: you personally read and type
every CAPTCHA. Instead:

1. A real, visible Chromium browser opens the search form.
2. The script auto-fills "Search By District", the state, and the district
   (open, unauthenticated dropdown APIs — no CAPTCHA involved), and focuses
   the CAPTCHA input box so you can start typing immediately.
3. The script waits — on the browser's own page-navigation event, not a
   terminal prompt — for **you** to read the CAPTCHA, type it in, and click
   Submit. No terminal interaction is required at any point.
4. Once your click navigates to the results, the script forces the results
   DataTable to show *all* rows via its own JS API (it defaults to paginating
   10-per-page client-side, which would otherwise silently truncate data),
   scrapes the table, and moves to the next district — reloading the page
   fresh so a new CAPTCHA is issued, since each search needs its own solve.
   If the result looks like a rejected CAPTCHA (no results table appears),
   it automatically retries (up to `--max-attempts`, default **5**) before
   giving up and moving to the next district.

Progress is saved after every single district, so stopping partway through
(Ctrl+C, closing the browser) never loses work.

## Setup

```bash
pip install -r requirements.txt
playwright install chromium
```

## Running everything: `run_all.py`

```bash
python run_all.py
```

That's it. It figures out what's left on its own:

1. Loads/fetches the full national state+district reference list (837
   entries, no CAPTCHA — open API).
2. Reads `output/pan_centers.json` to see what's already done.
3. Opens one browser window and walks every *remaining* district in order —
   auto-selecting state/district, waiting for you to solve each CAPTCHA
   (field pre-focused, just type and click Submit), scraping the full
   (pagination-expanded) results table.
4. After **every** district — success, failure, or skip — it rewrites
   `output/pan_centers.{json,csv,xlsx}` and rebuilds `progress_tracker.xlsx`.
   Nothing is batched or held back, so you can stop at literally any point.

Useful flags:

```bash
# Only work through one state's remaining districts
python run_all.py --state MAHARASHTRA

# Cap this run to N districts (e.g. a manageable session length)
python run_all.py --limit 25

# Adjust retry/timeout behavior (these are already the defaults)
python run_all.py --max-attempts 5 --timeout-minutes 10
```

Re-running `python run_all.py` with no arguments always just picks up where
you left off — completed districts (per `output/pan_centers.json`) are
skipped automatically, nothing needs to be tracked by hand.

## Lower-level: `scraper.py` (manual state/district targeting)

Only needed if you want to target something specific outside `run_all.py`'s
normal flow (e.g. re-scraping one district into an isolated folder to
inspect before merging).

```bash
python list_districts.py --state "MAHARASHTRA"     # prints district list + ready command
python scraper.py --state "MAHARASHTRA" --districts "..." --out-dir output_maharashtra
python merge_and_track.py output_maharashtra        # merge into output/, rebuild tracker
```

`merge_and_track.py` skips (and warns about) any district already present in
`output/` unless you pass `--force` to overwrite it — protects against
accidental duplicate rows if you re-run something by hand.

`scraper.py` knows the numeric IDs for all 33 states/UTs (`STATE_IDS` dict) —
just pass `--state "NAME"`.

## Output

`output/` holds the running national dataset:

- `pan_centers.json` — full records as JSON
- `pan_centers.csv` — same data as CSV
- `pan_centers.xlsx` — same data as Excel

Each record includes whatever columns the site's results table returns,
plus `_search_state` and `_search_district` indicating which query produced
it. Districts with zero centers still count as completed (0 rows) in
`progress_tracker.xlsx` — so "not attempted yet" and "checked, genuinely
empty" stay distinguishable.

## progress_tracker.xlsx

Two sheets, rebuilt automatically after every district by `run_all.py` (or
manually via `merge_and_track.py`):

- **Districts** — every district entry across all 33 states/UTs (837 total),
  with a ☑/☐ completion marker and record count per district.
- **States Summary** — one row per state: total districts, completed
  districts, total records, and a ☑/☐ fully-complete flag.

This is the source of truth for what's done nationally, and it's exactly
what `run_all.py` reads to decide what's left — you don't need to maintain
it by hand.

## Compliance notes

- No CAPTCHA bypass, OCR/vision-solving, or third-party CAPTCHA-solving
  service is used anywhere in this code, and none should be added — this
  applies regardless of who authored the solving logic.
- No attempt is made to work around the site's bot-mitigation layer — the
  script uses a genuine, visible browser session for every request.
- Runs are throttled with a short delay between districts. Don't remove this
  or run multiple instances in parallel against the site.
