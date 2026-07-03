# Recon Report — UTIITSL PAN PSA Center Locator

Target: `https://psaonline.utiitsl.com/PanPSACenters/forms/applicationCenters`
Date: 2026-07-03
Method: Direct HTTP inspection (curl) of HTML, JS references, and AJAX endpoints. No browser automation or CAPTCHA interaction was performed.

## 1. Page structure

The page is server-rendered (Spring MVC / JSP-style, note `;jsessionid=...` matrix params on every static asset — classic Java servlet container behavior). Key elements:

- A `<form id="transreport" action="processform" method="post">` — the search/results form.
- Two "Search By" modes via radio buttons: **District** (`radiovalue=Y`) or **Pin Code** (`radiovalue=N`).
- `<select id="state" name="state">` — **fully server-rendered**, all 33 states/UTs hardcoded in the initial HTML with numeric IDs (1–37, non-contiguous). No API call needed to get the state list.
- `<select id="dist">` and `<select id="pin">` — populated client-side via jQuery AJAX (empty in initial HTML).
- A CAPTCHA `<img id="captcha_id" src="captcha.jpg">` plus a text input `#captcha` (max 6 chars).
- A hidden field `<input name="id" value="...">` — a session-scoped token that changes on every page load (observed two different values across two fresh loads: `NdKFu98lxuYdUkO2DjBdgW06rNI`, `euWVTN08lttmglQPgEUuxQJIDHw`). Almost certainly a one-time submission/anti-replay token tied to the CAPTCHA session.
- `_csrf` / `_csrf_header` meta tags are present but **empty** in this deployment (Spring Security CSRF appears disabled or not populated for this form).
- Static assets (JS/CSS) are just UI libraries (jQuery, jQuery UI, DataTables, Bootstrap, SweetAlert2, a session-idle timer). No client-side business logic beyond the two AJAX calls below and basic form validation (`fieldValidation.js`, inline `validateCaptcha()`).

## 2. Discovered endpoints

| Endpoint | Method | Auth/CAPTCHA | Purpose | Response |
|---|---|---|---|---|
| `/PanPSACenters/forms/applicationCenters` | GET | None | Loads the search form + full state list | HTML |
| `/PanPSACenters/forms/loadDistByStateId/{stateId}` | GET | **None** | District list for a state | JSON array: `{"distId":"2","distName":"HYDERABAD"}, ...` |
| `/PanPSACenters/forms/loadPinByStateId/{stateId}` | GET | **None** | Pincode list for a state | JSON array: `{"pinId":"2","pincode":"500011"}, ...` |
| `/PanPSACenters/forms/captcha.jpg` | GET | Session cookie only | CAPTCHA image, session-bound | `image/jpg`, 135×35px |
| `/PanPSACenters/forms/processform` | POST | **CAPTCHA + hidden `id` token + session** | Submits search, returns center results | HTML (server-rendered results table via DataTables `#example`) — **not JSON** |

Verified live: `loadDistByStateId` and `loadPinByStateId` work with no cookies/captcha at all — they are open, unauthenticated JSON APIs. Confirmed 33 states, **837 total district-list entries** (some are messy/duplicate spelling variants of the same real district, e.g. "MAHABUB NAGAR" / "MAHABUBNAGAR" / "MAHBUBNAGAR" all under state 2 — this is dirty source data, not a scraping artifact).

Results (`processform`) are returned as a **server-rendered HTML page**, not JSON — there is no JSON/XML API for center details. The results table is built server-side and handed to DataTables purely for client-side pagination/search-within-page (i.e., pagination is cosmetic — all matching rows for that query come back in one response).

## 3. Bot mitigation observed

Every response (including plain GETs) carries:
- `Set-Cookie: TS0131a359=...`, `TS01940682=...` — hex-blob cookies with the `TS` prefix, the standard signature of **F5 BIG-IP / F5 Distributed Cloud (Shape) bot-defense** cookies.
- `Clear-Site-Data: *` on every response — instructs compliant browsers to wipe cookies/storage/cache after each response, which is an anti-session-replay measure.
- Strict `Content-Security-Policy`, `X-Frame-Options: DENY`, HSTS.

**Live test result:** A POST to `/PanPSACenters/forms/processform` with well-formed fields (valid state/district, a captcha guess, the current session's `id` token, realistic `Referer`/`Origin`/UA headers) was rejected with **HTTP 404 and an empty body, returned near-instantly** — consistent with a WAF/bot-defense layer dropping the request before it reaches the application, independent of whether the CAPTCHA text was correct. A plain GET to the same URL also 404s (POST-only route, as expected from the HTML form), so this doesn't by itself prove bot-defense, but combined with the TS cookies and instant empty 404 (no Spring "whitelabel error page" body, no validation error), it strongly suggests non-browser POSTs are filtered at the edge.

I did not attempt to probe further or find a workaround for this — that would cross into WAF/bot-defense evasion, which is out of scope per the ground rules.

## 4. Authentication

No login or API key is required anywhere in this flow. Access control is entirely CAPTCHA + session + (likely) bot-fingerprinting at the WAF layer.
