# v1.0.13 verification evidence

This folder contains the final evidence for the approved v1.0.12 → v1.0.13 lineup interaction update. It does not run as part of the application.

## Reproduce the application comparisons

Use fresh Python processes with the unchanged app requirements installed. Extract the v1.0.12 and v1.0.13 full ZIPs into separate directories. `SOURCE_112` and `SOURCE_113` below mean their respective `teals-sunday-pickem-main` directories. Run the probe from a writable working directory:

```text
python probe_release.py SOURCE_112 before_ordinary.json
python probe_release.py SOURCE_113 after_ordinary.json
python probe_release.py SOURCE_112 before_owner_1.json --owner --delay 0.04
python probe_release.py SOURCE_113 after_owner_1.json --owner --delay 0.04
```

Repeat the owner pair with output suffixes `_2` and `_3`, running each before/after pair sequentially. Keep the eight JSON files together and run:

```text
python compare_release.py DIRECTORY_WITH_JSON_FILES
```

The probe uses `tests/espn_performance_fixture.py`, which is present in both releases. It launches the full `app.py` with actual callbacks, routes and store methods; it substitutes anonymous database transport and a fixed application clock, and blocks outbound sockets. The owner name and UUID are synthetic. A shared initial shuffled card order lets independent sessions produce comparable cards. The comparator checks UI trees, saved picks, state/errors, ordered data queries, per-run owner authorization and run counts. No wall-clock timing threshold is used.

`comparison.json` records 44 ordinary scenarios plus three 47-scenario owner comparisons: 185 pairs. The owner samples include revocation, after which normal player actions remain permitted and the Commissioner tab disappears. Timings include artificial waits and instrumentation. The recorded protobuf bytes are server-generated messages before coalescing/compression, not wire traffic.

## Tests and package checks

```text
python run_tests_offline.py SOURCE_113 release.xml
python SOURCE_113/release_guard.py
```

Run the suite separately under Python 3.12 and 3.13. The included final logs are `release_312.log`/`.xml` and `release_313.log`/`.xml`: 479 tests passed, 22 existing dependency warnings, zero socket attempts. `rollback_313.log`/`.xml` records 446 passing tests after the documented rollback. `source_scope.json` records the implementation scope before release documentation/evidence was added.

`package_release.py` accepts four arguments: the exact v1.0.12 full ZIP, the completed v1.0.13 source directory, an output directory, and a scratch verification directory. It validates the baseline SHA, permits only the seven intended original-file changes, compiles the source, runs the release guard, builds both ZIPs, and checks the upload overlay and manual rollback against their expected bytes. It writes a package verification JSON and SHA-256 values for the ZIPs. It does not run or deploy the app, connect to production, or substitute for the separately logged regression suite.

The source tree includes old release evidence. Their commands and results describe those historical releases. Use the v1.0.13 paths above for this release.
