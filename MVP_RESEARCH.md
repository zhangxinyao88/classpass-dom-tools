# Programmatic ClassPass data and planning investigation

Checked 2026-11-12. No third-party server was installed or executed, no upstream
implementation code was copied into this project, no session credential was
exported/persisted, and no reservation was performed during the investigation.

Update: a separately built and cloud-verified Past DOM adapter is integrated
with the offline planner. The owning thread reported 100 of 126 displayed
cards (99 reservation variants, one order variant). The new bridge preserves
partial coverage, null years/timezones, unknown offering categories and
unverified attendance. See [PLANNING_MVP.md](PLANNING_MVP.md). The search-script
limitations below still apply to that separate search script. The private real
capture is not in this workspace or source bundle. The bridge has synthetic
end-to-end validation; the owning cloud thread subsequently verified the
in-place tool-result → stdin → planner flow with real history, an earlier search
snapshot and test configuration. See DOT_RUNNER.md for its exact limits.

## Exact scope of the existing DOM extraction

capture_search.js queries the ScheduleItem test ID and reads selected data-qa
fields: class title/link, studio title/link, optional instructor, displayed
start/duration, and the Reserve button's aria-label. It also reads the search
heading, source URL and capture timestamp. Python supplies year/timezone,
normalizes timestamps and parses a quote only from an exact matching label.

It reads all matching nodes currently mounted in the DOM, not just pixels in
the viewport. That may include offscreen or CSS-hidden mounted nodes. It does
not discover unmounted virtualized rows, trigger lazy loading, scroll, paginate,
visit another date/area, refresh inventory, read application state, inspect
requests or fetch account data. The heading/URL consistency guard is useful
but not an atomic backend snapshot.

| Data | Existing adapter |
| --- | --- |
| Mounted fitness search rows and displayed price labels | Implemented; original hardened cloud normal path returned 16 rows twice |
| All courses/venues/dates | No; complete_results=false |
| Seat availability/final checkout price | No; bookable=null |
| Category tags, distance, ratings, detailed policies | Not extracted |
| Past bookings, attendance, cancellation status, paid history prices | Not extracted |
| Balance, renewal boundary, rollover eligibility, expiry buckets | Not extracted |
| Food menus, modifiers, pickup windows and account food eligibility | Not verified by this adapter |

The cloud tests observed an existing page, not a new inventory refresh. There
is no measured token/latency benchmark. Deterministic parsing does not make
changing inventory or account-dependent prices deterministic.

## Existing GitHub projects: source review, not live verification

### dvcrn/mcp-server-classpass

[Repository/README](https://github.com/dvcrn/mcp-server-classpass),
[client](https://github.com/dvcrn/mcp-server-classpass/blob/main/classpass/client.go),
[reservation handler](https://github.com/dvcrn/mcp-server-classpass/blob/main/server/list_reservations.go),
[location handling](https://github.com/dvcrn/mcp-server-classpass/blob/main/server/location.go),
[license](https://github.com/dvcrn/mcp-server-classpass/blob/main/LICENSE).

This is the most relevant source map: it implements account/credit reads,
reservation reads, category/venue/item/slot search, food-tag search and write
tools. It uses the private mobile API, requires a password or authorization
token, and retains credentials/token in client memory. README examples would
put them in MCP configuration; that is not an adopted workflow here.

Important limits established from code:

- The method called AllBookings makes one request and is documented as the
  most recent 20 reservations overall, mixing past and upcoming. There is no
  history cursor loop in that method. It does not prove complete past history.
- Named-place resolution writes to the user's location history via PUT. Search
  paths can therefore have a write side effect even when described as read-only.
  The server also registers booking, cancellation and bookmark mutation tools.
- Booking normalization assumes raw class-reservation fields and drops the
  entity-type discriminator; food-history coverage needs independent checking.
- The client explicitly describes mobile-app impersonation and changing
  transport to get past curl fingerprint blocking. This investigation does not
  reproduce that behavior or treat it as permission to bypass the observed 403.
- AGPL-3.0 is present. Its implementation must not simply be copied into the
  existing MIT code and relabeled. We have copied no code; normal operation and
  a compatible reuse strategy would require separate evaluation.

Unverified source-level endpoint candidates, recorded as factual protocol
references only, not replay instructions or supported public API contracts:

| Capability | Candidate route from upstream source |
| --- | --- |
| Account | GET /v1/me/profile |
| Current credits | GET /v3/lifecycle/user/{id}/balance |
| Recent mixed bookings | GET /bff/v1/users/me/bookings?upcoming_only=false |
| Search layout | POST /unisearch/v3/layout/search |
| Categories | GET /bff/v1/tags |
| Tagged venue search, including food | POST /unisearch/v1/venues |
| Offerings and per-date schedules | GET /bff/v1/venue_offerings/{id}; GET /bff/v1/venue_schedule_list/{id} |

No authenticated request to these routes was made. HTTP method alone is not a
read-only guarantee; observed semantics and side effects must be reviewed.

### markswendsen-code/mcp-classpass and alirezahi/mcp-classpass

[First repository](https://github.com/markswendsen-code/mcp-classpass),
[browser source](https://github.com/markswendsen-code/mcp-classpass/blob/main/src/browser.ts),
[session source](https://github.com/markswendsen-code/mcp-classpass/blob/main/src/session.ts),
[package metadata](https://github.com/markswendsen-code/mcp-classpass/blob/main/package.json),
[second repository](https://github.com/alirezahi/mcp-classpass).

Both inspected main trees had the identical tree SHA
1977d6a9857c0c70aac2800d5570fded0552b007: they are duplicate source evidence,
not independent demonstrations. They use Playwright navigation, selectors and
clicks, including login, booking and cancellation. Search truncates to 30 cards.
Several exceptions become empty arrays, which could conceal a broken selector
or blocked page; a login success flag follows a fixed delay rather than a
verified account state. No separate food pipeline was found in the reviewed
session source. Browser setup includes anti-detection code and disabled security
isolation features; it is not adopted or run here.

package.json declares MIT, but the inspected full tree contains no LICENSE
file. Complete license/attribution provenance was not established, so no code
was copied. Their selectors differ from the ScheduleItem DOM observed in the
working cloud run; README claims are not proof they work on the user's account.

## Supported read-only history alternative: email

A narrow read-only search through the existing connected Gmail account returned
five ClassPass reservation reminders plus a continuation token. Two message
bodies were read in memory. They included event date/time, class and venue;
neither sampled reminder supplied paid credits or confirmed attendance. No
email bodies, IDs, links, account identifiers or real records were saved to this
project. Only this capability/result summary is retained.

This is a verified no-browser path to partial reservation evidence. It is not
proof of all bookings, final booking status, actual visits or complete history.
Duplicates, reminders, cancellation messages and timezone interpretation need
reconciliation. Do not score reminder presence as an attended or liked class.
Follow pagination only when doing a deliberate full import, keep source and
coverage markers, and leave unknown prices/statuses null. The planner currently
accepts normalized history; no general-purpose email-import parser is claimed.

Official help documents a web Upcoming/Past view and app Profile → Reservations:
[reservation help](https://help.classpass.com/hc/en-us/articles/205005635-How-do-I-know-which-reservations-I-ve-booked).
The owning browser thread can inspect those rendered pages normally and build
selectors from actual DOM. A UI list may still require load-more/pagination;
capture loaded_count, date coverage and completeness explicitly.

## Direct requests versus browser data

Direct structured responses would be more convenient for date/price/category
filters and pagination, if a permitted, working request source is available.
The earlier actual curl request to the public website returned Cloudflare 403;
no browser fingerprint evasion, mobile impersonation, alternate transport or
credential copying was attempted. That one response does not prove every
ClassPass endpoint is unusable, and third-party source does not prove another
endpoint is accessible or permitted from this environment.

This Codex session's current computer inventory again showed only its own two
empty browser surfaces, no dot cloud session. The owning thread previously
reported that its documented browser interface supports DOM reads and console
logs but no request/response observation API. No new normal authenticated request
trace could be obtained here. Do not inject fetch calls or use private CDP
connections as a substitute for a missing supported tracing capability.

Until an approved data interface is demonstrated, use the existing browser for
bounded, normal page acquisition and run all repeated filtering/planning over
local snapshots. This avoids repeated manual/visual clicks for each preference
change; it does not eliminate the browser's initial navigation, page rendering,
refresh or lazy-loading requirements.

## Next practical sequence

1. In the owning session, read the actual balance, renewal boundary, account
   rollover amount/eligibility and special credit conditions from the normal
   account view. Keep the ledger explicit; do not infer expiring credits merely
   from total balance. Official [rollover policy](https://help.classpass.com/hc/en-us/articles/209367426-Do-my-credits-roll-over)
   says next-cycle reservations use upcoming credits. It also distinguishes
   purchased and trial credits; account-specific terms remain relevant.
2. Read Past/Upcoming through observed DOM. Bootstrap missing reservation
   evidence from connected email, distinguishing bookings from attendance.
   Collect explicit likes/dislikes or ratings before claiming learned preferences.
3. Inspect one actual Food & Drink venue/item page, then one pickup-slot view.
   Determine menu/item/variant, pickup interval, current quote, eligibility and
   non-cancellation terms. Opening hours alone are not a reservable pickup slot.
   [Official Food & Drink help](https://help.classpass.com/hc/en-us/articles/17005226871949-What-is-ClassPass-Food-Drink)
   confirms selected-market paid-plan eligibility and non-cancellation. Current
   account access and menu DOM selectors have not been verified here.
4. Capture a bounded date/area shortlist, normalize classes and food separately,
   merge into the offline planner, and supply actual calendar windows/buffers.
   On new preference/time queries, rerun local code without revisiting each page.
5. Only if the owning environment exposes documented normal network observation,
   inspect one genuine read-only request in memory. Review method, route, body
   semantics, account side effects, pagination and 401/403 handling before any
   minimal adapter. No persistent credential configuration or write tools.

The new offline planner and its tested integration are concrete progress;
authenticated history/food/account collectors remain data-access tasks. No
MCP wrapper is implemented, and the workflow performs no booking actions.
