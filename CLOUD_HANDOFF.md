# Run in another environment

Copy the source directory or an archive containing only source, documentation, tests and synthetic examples. If a connected file service is used, follow its supported materialization workflow and retain the returned path. Do not transfer browser profiles, cookies, credentials, storage state, real captures or HARs.

~~~sh
python3 -m zipfile -e /returned/path/source.zip /tmp/schedule-demo
cd /tmp/schedule-demo/classpass-readonly
python3 -m unittest discover -s tests -v
~~~

Adjust the extracted directory name to the actual archive layout. Python 3.10+ and an IANA timezone database are required. The offline quick start in README.md needs no sign-in or network connection.

Browser capture additionally needs the exact runtime described in [CLOUD_DOM_ADAPTER.md](CLOUD_DOM_ADAPTER.md). A desktop terminal, a fresh browser, or an unconnected cloud shell does not inherit an existing browser session. This repository does not provision that runtime or transfer sessions.

Optional offline JavaScript checks require Node.js 18+:

~~~sh
node --test tests/test_capture.cjs
~~~

The normal-path browser workflow was tested twice on an existing rendered page. The five guard checks are offline harness tests, not live failure-branch tests. No refresh guarantee or standalone API availability follows from transferring the code.
