# ClassPass DOM Tools

**Food item schedules:** see [FOOD_ADAPTER.md](FOOD_ADAPTER.md) for
the separate studio/menu DOM contract, per-slot quotes, explicit planning blocks
and remaining limits. The suite passes 54 Python and 15 JavaScript tests. A
cloud browser-to-planner check read 26 food slots and selected one item without
an order. Policy fields remained unknown, and the displayed duration was not
treated as a pickup grace period.

**Current MVP focus:** credit-use planning across classes, food, time windows
and explicit/history-backed preferences. See [PLANNING_MVP.md](PLANNING_MVP.md)
for the runnable offline planner and [MVP_RESEARCH.md](MVP_RESEARCH.md) for
verified data-source coverage, upstream project review and remaining blockers.
No MCP wrapper is implemented; the focus is the read-only planning workflow.
The [dot runner recipe](DOT_RUNNER.md) connects supported browser capture results
directly to private stdin normalization, avoiding manual JSON copying. It still
requires the documented browser environment and an existing authorized session.

Experimental, read-only tools for normalizing rendered ClassPass schedule snapshots into compact JSON and filtering them locally. The browser-assisted path reads cards already rendered in an authorized session; it does not provide a standalone authenticated ClassPass API or MCP server.

This project is independent of ClassPass and is not affiliated with or endorsed by it. It contains no ClassPass logos, captured account data or session credentials.

## Status and scope

- Python 3.10+ and an IANA timezone database; no third-party Python packages.
- Optional browser capture requires a specific supported browser REPL, described in [CLOUD_DOM_ADAPTER.md](CLOUD_DOM_ADAPTER.md). It is not a standalone Node.js script or a general browser extension.
- Only cards present in the rendered DOM are captured. Results are partial snapshots, not guaranteed live inventory.
- Displayed credits can be account-dependent and can change. Bookability remains unknown.
- No sign-in automation, session export, bookings, cancellations, retries or access-challenge solving.
- Fifty-four Python tests and fifteen offline JavaScript tests pass. Cloud checks read search cards, partial history and one food item's slots through supported browser tools. Planner checks used test configuration, not a verified personal plan; failure branches use offline harnesses and inventory freshness is not guaranteed.

## Offline quick start

Save or extract the source into a working directory, then open a terminal in
that directory (the one containing classpass_cli.py). Verify Python with
python3 --version; Python 3.10 or later is required. There is no pip install,
API key, browser login or environment-file setup for the offline CLI. If the
system lacks IANA timezone data, install its timezone database package (often
named tzdata) before running a parser. Use python3 classpass_cli.py --help for
command help.

All bundled examples and test fixtures are synthetic. Names, paths, prices and timestamps in those fixtures are invented and are not offers or account quotes. Example URLs must not be fetched as real resources.

~~~sh
python3 classpass_cli.py parse-search examples/synthetic-search.json \
  --date 2026-11-13 --timezone America/New_York > /tmp/example-search.json
python3 classpass_cli.py filter /tmp/example-search.json \
  --after 16:00 --before 17:00 --keyword yin
~~~

Expected: one fictional class at 16:30, with a fictional 7-credit label and unknown bookability.

The separate studio-text adapter demonstrates the observed English schedule format:

~~~sh
python3 classpass_cli.py parse examples/synthetic-studio.txt \
  --source-url https://classpass.com/studios/example-fitness-studio \
  --date 2026-11-11 --timezone America/Los_Angeles \
  --studio "Example Fitness Studio" > /tmp/example-studio.json
~~~

These commands are offline. Python's parsed_at metadata changes per run; normalized class fields and filtering are deterministic for identical input.

## Commands

| Command | Behavior |
| --- | --- |
| parse-search | Validate and normalize captured search-card JSON. |
| parse | Parse the supported English studio text/simple HTML format. Does not execute JavaScript. |
| parse-history | Normalize rendered Past cards while preserving missing years and partial coverage. |
| parse-food | Normalize one food item's per-slot quotes or an explicit app-only notice; requires the food DOM contract. |
| filter | Filter normalized JSON by keyword and local start-time bounds. |
| inspect-har | Inspect an existing local HAR offline; emit only redacted route shapes, methods, status and counts. Does not replay requests. |
| fetch | Attempt one unauthenticated public-page GET. Stops on HTTP errors, including 403/429, and does not follow redirects or store cookies. |

Direct curl access returned HTTP 403 in the feasibility investigation. The browser-assisted adapter does not remove that restriction. An exact date/year and IANA timezone must be supplied because rendered headings omit information. Missing rows and unsupported formats fail rather than proving no availability.

## Tests

~~~sh
python3 -m unittest discover -s tests -v
node --test tests/test_capture.cjs
~~~

Node.js 18+ is optional for the offline JavaScript harness, not required by the Python CLI. Tests do not access ClassPass. Fake SECRET markers in tests are deliberately invented redaction fixtures.

The suites were exercised locally with Python 3.12 and Node.js 22 and also
passed in the browser-owning cloud environment. The declared minimum versions
have not been separately tested as a runtime matrix. See
[CONTRIBUTING.md](CONTRIBUTING.md) for fixture and change-review conventions.

## Data and sharing

Keep account snapshots, HARs, HTML captures, browser profiles, cookies and storage state outside version control. The ignore rules help with new files but do not remove already tracked files. Only the explicitly named synthetic JSON example is allowed by the broad JSON ignore rule. Do not include runtime snapshots in bug reports or release archives.

The filter command preserves the input object's other metadata; it is not a
privacy redactor. Use it on normalized parser output, and inspect any JSON
before sharing it. Even properly normalized snapshots can contain locations,
instructor names and account-dependent displayed prices. The CLI is a local
tool, not a hardened service for processing arbitrary uploaded files.

See [CLOUD_DOM_ADAPTER.md](CLOUD_DOM_ADAPTER.md) for the exact capture dependency and [CLOUD_HANDOFF.md](CLOUD_HANDOFF.md) for environment transfer.

## License and service terms

Original project code, documentation and invented fixtures are provided under
the [MIT License](LICENSE), copyright 2026 Xinyao Zhang. This source-code license
does not license ClassPass content, trademarks or account data, or grant access
to the ClassPass service. No third-party runtime code or captured service data
is bundled. The MIT text is the standard license documented by
[Choose a License](https://choosealicense.com/licenses/mit/).

ClassPass access is governed separately by its [current Terms of Use](https://classpass.com/terms/usa). As reviewed on 2026-11-12, section 7(m) restricts scraping/data-mining scripts and section 7(s) restricts automated access without express written permission. A normal signed-in session or an eventual source-code license does not establish that permission. The project does not claim that the browser workflow is authorized by ClassPass. Keep the permission question explicit before promoting or operating live automation; offline use of synthetic fixtures needs no ClassPass connection.
