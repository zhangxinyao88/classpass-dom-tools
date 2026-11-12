# Credit-use planning MVP

Current priority: a useful programmatic planning workflow. No MCP wrapper is
required or implemented.

## What works now

credit_planner.py is an original, standard-library-only offline planner. It
combines supplied class and food opportunities with explicit time windows,
calendar conflicts, travel gaps, a current credit budget, a caller-confirmed
spend target, preferences and normalized history. It neither accesses ClassPass
nor books anything. All bundled examples are invented.

```sh
python3 credit_planner.py examples/synthetic-plan.json
```

Expected demonstration: select the fictional five-credit class and three-credit
coffee pickup, use eight of twelve credits, leave four, and execute zero actions.
This proves the planning logic, not real restaurant inventory or account history.

## Input semantics

- available_credits: current account balance, supplied explicitly.
- credit_cycle_ends_at: exact renewal boundary with UTC offset; must be after
  as_of. To count toward the current-cycle plan, opportunities must finish by
  this boundary. A next-cycle reservation is not treated as spending the current
  balance. See the official [rollover explanation](https://help.classpass.com/hc/en-us/articles/209367426-Do-my-credits-roll-over).
- spend_target: credits the caller wants to use, not an inferred expiry amount.
  Read actual rollover eligibility/amount, cycle date and any special-credit
  conditions before setting it. A remaining balance is not automatically waste.
- available_windows / busy_windows: explicit ISO timestamps with UTC offsets.
  Availability must cover the entire class or pickup slot. The planner does
  not connect a calendar itself or compute route times.
- preferences: keyword and exact venue weights (-100 to 100), excluded keywords,
  max_events (0–8), per-item credit limit and minimum_gap_minutes (0–180).
- opportunities: id, kind (class or food), name, venue, starts_at, ends_at,
  credits; optional bookable=false explicitly excludes an unavailable option.
  A missing quote is excluded rather than filled from history. Unknown
  bookability remains unknown even when a plan is returned.
- history: manually verified records with kind, venue, name, status and optional
  paid credits/rating. Only attended/completed records count as visits. Explicit
  1–5 ratings can influence preference; a booking, reminder, cancellation,
  unrated past card or repeat attendance is not automatically treated as liking.
  The optional history bridge below also supplies rated past cards without
  claiming attendance. Paid and merely displayed historical prices are reported
  separately and never replace a current quote.

Food is excluded unless allow_nonrefundable_food is explicitly true. This is a
planning acknowledgement, not authorization to place an order. Food requires
the actual selected item's pickup slot, not general venue opening hours.
The official [Food & Drink explanation](https://help.classpass.com/hc/en-us/articles/17005226871949-What-is-ClassPass-Food-Drink)
describes item/pickup reservations and non-cancellation; menu items and final
prices still need account-specific verification. This MVP does not verify
ingredients, dietary suitability or out-of-pocket add-ons.

## Search snapshot integration

The planner can append an existing classpass_cli.py parse-search result. The
operator must explicitly classify that snapshot as class or food; this option
does not prove that a food page uses the fitness search-card format.

```sh
python3 credit_planner.py /path/to/planning-config.json \
  --search-snapshot /path/to/normalized-search.json --kind class
```

The planning config supplies the account/time/preferences/history fields above;
opportunities can be omitted or can contain independently captured food slots.
The search bridge maps studio to venue and source_url to the candidate ID.
No new browser fetch occurs. Current food and account capture still need
separately observed adapters; no fictional live selectors are claimed for them.

## Integrated past-history adapter

The separately built [history adapter](HISTORY_ADAPTER.md) is now integrated
without replacing the version 6 planner. A cloud normal-path check reported
100 captured cards against a displayed total of 126: 99 reservation-card
variants and one order-card variant. This remains partial, and a reservation
variant can also represent food. The source archive contains no real capture.

```sh
umask 077
python3 classpass_cli.py parse-history /private/path/raw-history.json \
  > /private/path/normalized-history.json
python3 credit_planner.py /private/path/planning-config.json \
  --search-snapshot /private/path/normalized-search.json --kind class \
  --history-snapshot /private/path/normalized-history.json \
  > /private/path/plan.json
```

Use an existing private task directory (mode 700); files and outputs should be
mode 600. None of these commands fetches a page or books an item. The planning
config still needs actual balance, renewal boundary, target and availability;
the history snapshot does not provide them.

history_bridge.py retains each card's displayed date, null year/timezone and
card variant. It sets offering kind to unknown and status to past_listed.
Historical displayed credits are kept separately from confirmed paid credits.
Explicit ratings match the current candidate by item and venue text; matching
does not establish category, attendance, recency or a unique booking identity.
No chronological ordering, year inference or silent deduplication is performed.
Do not import the same snapshot twice or duplicate it in manual history.

The result propagates captured/displayed counts, variant counts, unknown-year
count and complete_history=false under history_coverage. It reports matching
past cards separately from confirmed completed visits. Missing ratings do not
raise preference, and old displayed prices never fill a missing current quote.

Local integration validation uses synthetic end-to-end fixtures, including a
100-of-126 shape with 99/1 variants. The owning cloud thread subsequently
verified a fresh real history capture → stdin normalization → planner flow with
the earlier search snapshot and a clearly labeled test configuration. No human
copied JSON. The private capture was not transferred to this review host or
bundled in source, and test configuration is not a personal recommendation.
See [DOT_RUNNER.md](DOT_RUNNER.md) for the supported-tool handoff recipe.

## Deterministic selection

After validation and filtering, at most 20 eligible opportunities are accepted.
The exact bounded search respects budget, time overlap, gaps and maximum events.
It first covers as much of the explicit spend target as possible, then favors
explicit preference utility, then lower spend on a tie. Negative-preference
options are excluded so an expiry target does not force a known disliked choice.
IDs resolve exact ties deterministically. More than 20 eligible options is a
clear error requiring a narrower shortlist, not silent truncation.

The objective is a transparent MVP heuristic, not an established personal
utility model. It has no fatigue limits per activity/day, route optimizer,
dietary verification or multi-cycle ledger yet. Configure max_events, windows
and exclusions before using real candidates. Outputs apply only to supplied
candidates, mark freshness unvalidated and history completeness unknown, and
report target shortfall rather than inventing a feasible offer.

## Tests and data boundaries

```sh
python3 -m unittest discover -s tests -v
```

Planner tests cover class/food combination, no automatic food ordering, travel
and calendar conflicts, unknown current prices, rating/attendance distinctions,
negative preferences, rollover-aware cycle cutoff, zero-target behavior,
malformed input, integration with existing normalized search output, and the
new raw-history → normalization → planning bridge. The integrated suite has
42 Python tests and eight offline JavaScript capture tests.

Use private task-local files for real input/output. The planner does not write
credentials or make network requests, but its stdout can contain sensitive
history and preferences. Do not commit those files or share them as examples.
