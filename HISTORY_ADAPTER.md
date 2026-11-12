# Read-only history adapter

Integrated with the version 6 planner; see [PLANNING_MVP.md](PLANNING_MVP.md)
for the private-file data flow. The merged project has 42 Python tests and
eight offline JavaScript tests. The original standalone test counts are
historical. The merge does not infer missing years, categories or attendance.

Run `capture_history.js` through the supported browser REPL with the existing authorized `https://classpass.com/profile/past` tab bound as `tab`. Read current browser documentation and inspect the page before capture. This is not a standalone Node browser client. The capture only reads rendered reservation/order cards and the displayed Past count. It does not click booking, rating, or account controls and exports no cookies, credentials, booking IDs, account name, images, or hidden application state.

Save the emitted JSON locally outside this source tree, in a private directory (mode 700) and file (mode 600). Run:

```sh
python3 classpass_cli.py parse-history /private/path/history.json > /private/path/normalized.json
```

Protect the output similarly. Normalization includes item/class, venue, optional instructor, credits, rating (1–5 or null), and date exactly as displayed. Year and timezone stay null. No chronology across years is inferred. Historical food prices are not current menu prices, and the `reservation` card variant is not equivalent to fitness: older food purchases also use it.

Live verification on 2026-11-12 captured and normalized 100 cards: 99 reservation variants and 1 order variant. The profile displayed Past (126), so coverage is explicitly partial. No pagination or completeness beyond rendered DOM was verified. `complete_history` remains false even if a future count matches the header. Header/URL stability checks do not make multiple DOM reads atomic.

The live capture is kept locally outside the distributed source archive. Tests use synthetic examples only. Run Python tests with `python3 -m unittest discover -s tests -v` and browser-script harnesses with `node --test tests/*.cjs`. Offline tests cover malformed inputs, both variants, ratings, dates without year inference, allowlisted output fields, source validation, empty results, and page changes. Live verification exercised normal capture and normalization, not deliberately induced site errors.

Food venue web pages may say ordering is limited to iOS/Android. History extraction does not supply current app-only menus or ordering access. No account changes or credential persistence are implemented.
