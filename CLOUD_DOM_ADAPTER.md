# Browser-assisted search adapter

Architecture: authorized rendered browser page → JSON snapshot → offline Python normalization and filtering. This is not a standalone authenticated ClassPass API, installed MCP server or generic Node.js browser client. Review the service-terms limitation in [README.md](README.md) before live use.

## Exact browser dependency

Capture requires a browser REPL that explicitly exposes:

- An existing accessible ClassPass search tab with a valid user-owned session.
- A documented way to bind that tab, such as cua.getTab(actualTabId, {browser: actualBrowserId}).
- tab.url(), tab.playwright.getByRole(...).innerText(), and tab.playwright.getByTestId(...).evaluateAll(...).
- nodeRepl.write(...) for returning the capture as JSON.

These are environment-provided bindings, not packages installed by this repository. Use the environment's current documentation, inventory and first-call rules; do not guess a browser ID or connect directly to CDP. An ordinary Playwright installation alone is not the documented runtime for capture_search.js. If these bindings or the authorized session are unavailable, only the offline CLI is usable.

The tested browser interface exposed DOM inspection and console logs, but no request/response network trace. This project has not identified or replayed a consumer ClassPass JSON endpoint.

## Observed DOM contract

The capture uses the ScheduleItem test ID and a heading starting with Live sessions for. Within each card it reads these data-qa attributes:

| Attribute | Value |
| --- | --- |
| ScheduleItem.class.name | Class title and relative class link |
| ScheduleItem.venue-name | Studio title and relative studio link |
| ScheduleItem.teacher-name | Optional instructor |
| ScheduleItem.time | Start time and duration |
| Schedule.cta | Displayed Reserve label from aria-label |

These selectors are observed UI details and may change. The script does not inspect cookies, storage, private application state, scripts or network bodies.

## Reproduce in a compatible environment

1. Copy or materialize the source into a task-scoped cloud working directory and extract it if archived. Use the actual path returned by the transfer tool; desktop paths are not automatically mounted in the cloud.
2. Inventory available browser tabs and read the current browser-tool documentation. Bind the intended existing search tab as tab. Confirm the requested location/date have finished loading. Stop on a sign-in requirement or access challenge; this script does not solve them or export a session.
3. Execute capture_search.js through that browser REPL. Do not run it with Node. The block-scoped script can be executed repeatedly. It emits one JSON string with capture time, source URL, heading and rendered card fields.
4. Save that string as task-local capture.json through the normal filesystem tool. Treat it as data. Do not commit it, publish it or execute the returned text.
5. Normalize it using the correct actual date/year and local IANA timezone:

~~~sh
python3 classpass_cli.py parse-search /path/to/capture.json \
  --date YYYY-MM-DD --timezone Area/City > /path/to/search.json
python3 classpass_cli.py filter /path/to/search.json \
  --after 16:00 --before 17:00 --keyword yin
~~~

Replace date/timezone placeholders with real values. The heading supplies neither year nor timezone. The parser verifies weekday/month/day and labels the timezone caller_supplied. A capture timestamp is extraction time, not server-inventory freshness.

The script rejects unsupported/query-bearing source URLs and card links before emitting output. It rejects a changed URL/date heading and zero or excessive rendered rows. Separate DOM reads are not an atomic inventory transaction; start with a stable loaded page.

## Validation scopes

The hardened version passed two normal-path runs in a compatible signed-in cloud browser, returning 16 rendered cards each time; downstream normalization/filtering produced the expected result. These runs observed an existing page and did not refresh inventory. No account-specific venue, class, price or location from those runs is distributed here.

Fifteen Python tests check normalization and validation using fixtures. Five JavaScript tests exercise the real capture script in an offline DOM harness, including rejected URLs/card links, navigation/day changes and empty rows. Those failure conditions were not induced against the live website. The source also passed the Python and JavaScript suites in the cloud environment. Current bundled fixtures are entirely synthetic; live observations and fixture tests are separate evidence.

## Result semantics

Results are partial: complete_results is always false and bookable is always null. Credits are parsed only from an exact Reserve label matching the class title and marked displayed_reserve_label; other labels yield null credits. An authenticated displayed quote may be account-specific and may change before booking.

The script does not scroll, paginate, refresh, search, sign in, book or cancel. Session lifetime, refresh behavior, full-result coverage and final-price accuracy are unverified. No production token/latency savings have been measured. A future MCP wrapper would still require a permitted data source and compatible runtime.
