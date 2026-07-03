# CAPTCHA Analysis — UTIITSL PAN PSA Center Locator

## Behavior

- **When it appears:** Immediately — the CAPTCHA image loads as part of the initial `applicationCenters` page, before any search is performed. It is not deferred to a second step.
- **What it is:** A server-generated JPEG (135×35px) served from `/PanPSACenters/forms/captcha.jpg`, tied to the current `JSESSIONID`. A refresh link reloads it with a cache-busting query param (`captcha.jpg?<random>`), which almost certainly regenerates the expected answer server-side for that session.
- **Where it's checked:** Client-side JS (`validateCaptcha()`) only checks the field is non-empty before allowing form submit — the actual answer validation happens server-side on POST to `processform`.
- **Session scope:** One CAPTCHA image corresponds to one session (`JSESSIONID` cookie). Alongside it, the form carries a hidden `id` token that changes on every fresh page load, suggesting each CAPTCHA challenge is paired with a one-time submission token — i.e., **likely single-use**: solving it once probably authorizes exactly one `processform` submission, not repeated/unlimited searches. This could not be fully confirmed without performing an actual CAPTCHA solve + submission, which requires human input per the ground rules.
- **Multiple searches:** Given the token appears to be regenerated on every page load and there's no visible "search again without reloading" affordance in the JS (no AJAX call for `processform` — it's a full form POST/page navigation), each new search almost certainly requires a fresh page load → fresh CAPTCHA → fresh solve. There is no evidence of a "solve once, query many times" session mode.

## Additional access control beyond the CAPTCHA itself

Independent of the CAPTCHA, the `processform` POST endpoint appears to sit behind bot-mitigation infrastructure (F5/Shape-style `TS`-prefixed cookies, `Clear-Site-Data: *` on every response). A well-formed POST from a plain HTTP client (correct fields, realistic headers, valid session cookies) was rejected with an immediate empty 404 — before CAPTCHA correctness would even matter. This means **a real browser session (or an automation tool that fully replicates one, e.g. Playwright/Selenium) is required to reach the results endpoint at all**, on top of needing a human to read and enter the CAPTCHA text.

## Conclusion

- CAPTCHA cannot be bypassed, solved automatically, or farmed out to a solving service (per ground rules), and independently there's a WAF layer that likely also requires genuine browser fingerprinting.
- The only compliant path to the actual results (`processform`) is: **real browser session + human reads and types the CAPTCHA for each search.**
- The state/district/pincode list APIs (`loadDistByStateId`, `loadPinByStateId`) are fully open and require no CAPTCHA — these can be fetched directly and instantly via plain HTTP.
