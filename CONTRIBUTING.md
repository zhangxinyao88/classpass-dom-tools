# Contributing

Keep the scope read-only: snapshot validation, normalization, local filtering
and small browser adapters for documented compatible runtimes. Do not introduce
bookings, cancellation actions, credential collection, session export,
challenge bypasses or generic authenticated request replay.

Run the offline suites from the directory containing classpass_cli.py:

```sh
python3 -m unittest discover -s tests -v
node --test tests/test_capture.cjs
```

Python 3.10+ and timezone data are required. Node.js 18+ is optional for the
JavaScript harness. No test needs a live account or network access.

Use invented fixtures. Do not submit actual search captures, account quotes,
HAR files, browser state, cookies, tokens, personal paths or private contact
details in source, issue reports or attachments. Existing SECRET markers are
explicitly fake redaction-test inputs. Describe problems with a minimal
synthetic reproduction. Ignore rules do not clean previously committed data.

For browser changes, report the exact documented runtime and whether validation
used a normal live path or the offline harness. Do not treat a captured DOM
snapshot as proof of refreshed inventory, final pricing or ClassPass permission.
Review the service-terms limitation in README.md before any live operation.

This repository does not provision the browser runtime or private disclosure
infrastructure. Do not include sensitive exploit data in public discussions;
arrange a private reporting channel with the maintainer first if needed.
