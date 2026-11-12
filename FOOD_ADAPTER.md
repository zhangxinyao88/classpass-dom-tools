# Read-only food item schedules

This is a distinct studio/menu adapter; a zero result from the fitness
ScheduleItem extractor does not establish that food is unavailable.

## What was verified

The ordinary in-app browser could open a normal food studio page using its
existing signed-in session. No password, cookie, token or hidden app state was
read. DOM inspection established a different Schedule/Section/ScheduleRow
contract from fitness search. After one normal date navigation and bounded
load-more actions, the capture logic returned 17 mounted slots for one selected
item, five with explicit quotes. Quotes differed by time. Those real captures,
item names, prices and account details are not included in fixtures or this
source package.

The local tests cover normalization → mode-600 private ingest → planner using
synthetic data. The owning dot thread subsequently verified the full supported
browser DOM → Python normalization → planner flow on 26 real food slots. It
selected one quoted item without duplicating its alternative times and placed
no order. All 54 Python and 15 JavaScript tests passed in that cloud check.
The test configuration was not a personalized recommendation. No real captures,
menu prices, account values or planning configuration are bundled here.

Policy text was separate from those slots and was not supplied to normalization:
noncancelable and no_credit_refund_after_order therefore remained unknown. The
displayed 60-minute label was not interpreted as a pickup grace period. This
normal-path check is not a test of every failure branch or proof of complete or
refreshed inventory. App-only behavior has an offline test and a public page
notice, not a new live signed-in app-only capture in this review.

## Capture contract and observed selector profile

Bind the existing authorized tab through the supported browser tool and inspect
its current page. In that same browser REPL, define foodSelectors from observed
DOM. Do not run capture_food.js with Node or guess a selector profile from a
different page. The script refuses to emit web slots without a food-context
confirmation and explicit mappings.

For the observed studio schedule layout, this profile uses actual inspected
attributes. Replace only the item name after confirming its exact visible text:

```js
let foodSelectors = {
  confirm_food_context: true,
  layout: 'schedule_rows',
  scope: '[data-testid="Schedule"]:has(> section[data-testid="Section"])',
  date: '[data-qa="DateBar.date"]',
  slot_rows: ':scope > section[data-testid="Section"]',
  item_name: '[data-qa="ScheduleRow.className"]',
  item_exact_name: '<exact observed food item name>',
  slot_time: '[data-qa="ScheduleRow.date"]',
  slot_credits: '[data-qa="Schedule.cta"]',
  credits_attribute: 'aria-label',
  slot_action: '[data-qa="Schedule.cta"]',
  policy: null
};
```

The extra child condition makes the scope unambiguous because the observed
page had two nested Schedule elements. Native CSS :has support is required for
this profile. The exact item filter runs before any slot price is used, so
another menu item's quote cannot be assigned to the selected item. Only mounted
rows are read; the script does not choose dates, load more or paginate itself.

An alternative layout, selected_item, handles a scope containing one item
heading and multiple time rows. For that layout item_name is read from the
scope; in schedule_rows it is read from each row and compared to item_exact_name.
Tests use invented selectors rather than pretending they are site attributes.

After binding tab and foodSelectors, execute capture_food.js. It reads only
visible text and selected accessibility attributes, exports no checkout links
or order IDs, and checks URL/date stability. This is a DOM snapshot, not a
backend transaction. A recognized app-only notice emits availability=app_only
with zero web slots; it does not claim zero food inventory or suggest a bypass.

## Normalize and plan offline

All examples below are fictional. The 15-minute block is an illustrative
planning input, not a pickup deadline or a verified travel estimate:

```sh
python3 classpass_cli.py parse-food examples/synthetic-food.json \
  --date 2026-11-13 --timezone America/New_York --block-minutes 15 \
  > /tmp/synthetic-food-normalized.json
python3 credit_planner.py examples/synthetic-food-plan.json \
  --food-snapshot /tmp/synthetic-food-normalized.json
```

Expected: one fictional six-credit pickup choice, not three repeated orders.
Real captures should use private directories and the stdin ingest path:

```sh
python3 ingest_capture.py food --output /private/path/food.json \
  --date YYYY-MM-DD --timezone Area/City --block-minutes N < /private/path/capture.json
python3 credit_planner.py /private/path/config.json \
  --food-snapshot /private/path/food.json \
  --search-snapshot /private/path/search.json --kind class \
  --history-snapshot /private/path/history.json
```

Replace placeholders with verified values. ingest_capture.py atomically writes
normalized mode-600 output and requires a private parent directory. It prints
counts/status, not menu contents. For a recognized app-only capture, the date,
timezone and block arguments are unnecessary. In run_dot_capture.js use food
mode, set the verified day/timezone and foodBlockMinutes for a web schedule,
and bind foodSelectors in the browser REPL before invocation.

## Quote, time and policy semantics

- Each slot carries its own current displayed quote. Only a plain credit label
  or an exact Order/Reserve label matching the item name is parsed. Missing,
  starting-from, multi-price or unsupported labels stay unknown. Historical
  prices and other items' prices are never substituted.
- Weekday/month/day must match the caller-supplied year/date. IANA timezone is
  caller-supplied and any displayed abbreviation must agree. Ambiguous DST
  times fail. A date mismatch does not silently become today's schedule.
- The explicit planning block determines ends_at. A displayed 60 min label is
  retained separately and is not treated as a verified pickup deadline or time
  spent eating. pickup_window_ends_at remains null. Verify actual pickup terms
  independently; this MVP selects the advertised slot start and does not choose
  an arbitrary arrival time within an assumed window.
- A disabled displayed action is conservatively excluded. An enabled action
  leaves bookable unknown; it is not a checkout/eligibility guarantee.
- The same item/venue/day shares a mutually exclusive choice_group. At most one
  alternative slot can be selected. Current menu variants/modifiers must be
  represented by their exact independently observed item names; they are not
  expanded or inferred by this adapter.
- A more expensive quote for the same item does not gain preference merely by
  using more credits. Target coverage uses the lowest eligible quote in that
  food choice group as a reference; actual budget/spend still uses the selected
  slot's real quote. A costlier time can still win if it permits a better
  overall schedule. reference_credit_coverage is not money or actual spending;
  planned_credits and projected_credits_remaining retain their ordinary meaning.
- Non-cancellation/no-refund flags are set only when the mapped policy text
  explicitly supports them. Missing policy text stays unknown, not refundable.
  The live schedule check did not capture checkout policy. Food is excluded by
  the planner unless allow_nonrefundable_food is explicitly true regardless of
  these flags. That acknowledgement does not authorize an order.

## Remaining limitations and future checks

1. Reconfirm selector/profile uniqueness and exact item matching after a UI
   change, including price labels from different times.
2. The supported-tool food-mode handoff has passed its normal-path cloud test.
   Actual cancellation and pickup policy remain separate read-only evidence;
   do not attach policy from another item/date or press Reserve/Order to test.
3. Verify an app-only venue returns the explicit app_only state and no fabricated
   menu/slots; do not bypass the app restriction.
4. Narrow time windows if more than 20 eligible planner candidates remain. The
   source stays partial; no global menu coverage or unattended operation is
   claimed. Review the changed objective and user preferences before treating
   a test plan as a personal recommendation.

No credential access, authenticated request replay or booking is implemented.
Publishing the source does not grant service access permission; existing
service-permission limits still apply.
