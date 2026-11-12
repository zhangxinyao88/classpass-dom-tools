# Repeatable dot-cloud workflow

The cloud environment already has Python and the source files. No package installation is needed. The supported browser tool owns access to the existing signed-in browser. This project does not launch browsers, attach directly to CDP ports, export credentials, or automate login.

1. In dot's browser tool, inspect current inventory with `await cua.getState()`. Select the exact existing ClassPass target using `let tab = await cua.getTab(actualId, {browser: actualBrowserId})` and inspect its current page. Use identifiers from the runtime rather than assuming `cdp` exists. Read current browser guidance. If REPL state reset, initialize it again. The supplied scripts require a `tab` binding.
2. Execute `run_dot_capture.js` in dot's functions orchestration runtime, with project path/mode/output adjusted for this workspace. The distributed project path is a placeholder and the recipe refuses to run until replaced. For search, also supply the verified date and timezone. This is an agent-runtime recipe, not an executable Node CLI. It invokes the supported browser tool, captures the JSON tool response, and feeds it directly to Python without human copying or model transcription.
3. `ingest_capture.py` normalizes the data received on stdin and atomically writes only the normalized result with mode 600. Parent output directory must be private (700); a missing directory is created privately. It prints only counts/status, not raw history. Failed input leaves an existing output untouched.
4. Run the planner with that file and an existing normalized search snapshot/config:

```sh
python3 credit_planner.py /private/config.json \
  --search-snapshot /private/search.json --kind class \
  --history-snapshot /private/history.json > /private/plan.json
```

Use `umask 077` and a private directory for planner output. The config must state verified balance/cycle boundary and user-approved target/availability/preferences. Test configs are not personal recommendations.

Verified here: direct live history capture and stdin normalization returned 100 cards versus displayed 126, then the planner consumed that fresh normalized history alongside the previously captured 16-card search. No human copied JSON. Search acquisition is still separate: its UI filters must already be set and the current page inspected. No automatic multi-date search, pagination, current food-menu capture, or reliable session renewal exists.

## Persistence

The code and private files exist in this selected cloud workspace, not on the user's laptop. An active signed-in browser is required only for capture; offline processing continues without browser access. Browser handles can reset after inactivity, tabs can close, login can expire, and an execution workspace can be replaced. No restart/reboot persistence guarantee has been tested. Library source archives can restore code, but do not restore sessions or private captures.

This is repeatable on demand through dot's tools, not an installed daemon, autonomous service, registered MCP server, or scheduled monitor. Do not claim independent unattended operation. No scheduler or credentials were installed. A browser challenge, unsupported page, or expired session stops capture; there is no HTTP/403 bypass fallback. Existing service permission constraints still apply.
