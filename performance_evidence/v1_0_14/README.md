# v1.0.14 performance evidence

These files validate the implemented release against the byte-verified v1.0.13 archive. The earlier proposal's in-memory candidate installers and rejected nested-picks optimization are not used here.

## Results

- `release_312.log/.xml`, `release_313.log/.xml`: 555 passing tests on each interpreter, with outbound sockets blocked by `run_tests_offline.py`.
- `rollback_313.log/.xml`: all 479 original tests pass after restoring eight original files and deleting the four new test/fixture files.
- `comparison.json`: 76 complete-app pairs and 36 downstream consumer pairs pass. `compare_release.py` reproduces comparisons from raw JSON; run counts, writes and exact displayed output are checked.
- `source_verification.json`: four runtime files changed, all other original files except the four documented test/fixture updates remain identical; exact legacy loader and cache coordinator preservation.
- `resolved_dependencies_312.json`, `resolved_dependencies_313.json`: actual installed packages; application requirements unchanged.
- `live_*_smoke.json`: ordinary player, no artificial wait, 17 screens/actions per source.
- `live_*_owner_{1,2,3}.json`: three paired linked-owner samples, 40 ms per synthetic database operation, 17 screens/actions each.
- `due_*.json`: one paired successful ESPN refresh; 40 ms database waits, 60 ms per summary request, ten requests/three workers, exact updated clock/score/week outputs.
- `transitions_*.json`: six additional paired views around a tap followed by a phase, account or next-week change.
- `consumers_*.json`: 12 public-data/consumer/state fingerprints for 0/1/15/50 participants, missing-profile/empty-pick scenarios and 30 equal-name/count permutations; three standalone cold-bundle timings each.

Raw UI trees normalize runtime widget/form/fragment IDs and the intentional Build label only. Consumer bundle profiles are compared by ID because the original profile query has no ordering guarantee; picks retain exact order. No production SQL, real provider, physical browser or AWTRIX hardware was contacted. Provider refresh remains synchronous in its elected session.

## Reproduce in an isolated developer workspace

These commands are for maintainers. Michael installs with the browser steps in `START_HERE_v1.0.14.md`.

Use the unchanged v1.0.13 archive (SHA-256 `0bcc45369873b82bd049c7709f5e35e6099c1027edd8b4110b02376e293d2022`) and this release. Create Python 3.12/3.13 environments from the unchanged `requirements.txt`. Copy this evidence directory to a temporary working directory before rerunning, so original evidence remains intact. Substitute the actual absolute paths below.

```bash
python EVIDENCE/run_tests_offline.py RELEASE OUTPUT/release.xml
python EVIDENCE/probe_live_bundle.py BASELINE EVIDENCE/live_baseline_smoke.json --variant baseline
python EVIDENCE/probe_live_bundle.py RELEASE EVIDENCE/live_release_smoke.json --variant release
python EVIDENCE/run_comparisons.py BASELINE RELEASE
python EVIDENCE/probe_transitions.py BASELINE EVIDENCE/transitions_baseline.json --variant baseline --owner
python EVIDENCE/probe_transitions.py RELEASE EVIDENCE/transitions_release.json --variant release --owner
python EVIDENCE/probe_consumers.py BASELINE EVIDENCE/consumers_baseline.json
python EVIDENCE/probe_consumers.py RELEASE EVIDENCE/consumers_release.json
python EVIDENCE/compare_release.py
python EVIDENCE/verify_source.py BASELINE RELEASE BASELINE_ZIP OUTPUT/source_verification.json
```

The probes execute the actual source functions. Only transport/data fixtures, clock dates and instrumentation are supplied. `public_query_fixture.py` models explicit selected columns/default left-join JSON; it is not a PostgreSQL engine. `public_bundle_fixture.py` supplies anonymous fixtures and consumer fingerprints. Runtime functions are never replaced with candidate optimizations. The complete app's store constructor is bound to synthetic storage for AppTest, and outbound sockets are blocked.

The package builder takes `BASELINE_ZIP RELEASE OUTPUT_DIR SCRATCH_DIR`. It validates tests/comparisons and allowed files, compiles Python, runs the release guard, verifies both ZIP payloads, extracts and overlays the browser upload onto the baseline, and checks the resulting files against the full package. It also checks rollback bytes. The browser ZIP carries `PACKAGING_VERIFICATION.json` outside `UPLOAD_TO_GITHUB`; artifact hashes are in the separate package verification output.

Time measurements include AppTest overhead. Do not extrapolate the synthetic milliseconds or percentage differences to production Sunday latency. Regression tests use counters and exact outputs rather than timing thresholds.
