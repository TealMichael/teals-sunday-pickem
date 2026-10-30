# v1.0.13 — lineup interaction performance release

The approved lineup changes are complete. Build/Continue, Edit Lineup, Next, Back, entering or changing an emergency backup, returning to Review/Lineup, and Save My Lineup now resolve during the normal click-triggered page run. Successful ordinary transitions no longer generate the departing screen and then restart the entire app.

Version **1.0.13**, build **1.0.13-performance4**, proposed tag **v1.0.13**. Commit message: `perf: avoid duplicate lineup navigation and save reruns in v1.0.13`.

## Implementation and preserved behavior

Buttons stage a single-use intent containing scalar origin information. Callbacks make no database reads or writes. The authenticated player route consumes the intent before early returns and checks the current account/session, render generation, mode, position, return destination, week, phase, pool and lineup before applying it. Stale requests are discarded and never replayed.

Saves use the existing `_save_selected_position`, `store.save_pick` and `store.confirm_lineup` paths. A card tap remains staged until Next; a questionable starter and backup save together; Back discards an unconfirmed choice; unchanged choices skip writes. A failed save leaves the original screen and staged choice with the error in its original location, requiring an explicit retry.

Home-origin actions retain the current pregame status/recovery read and `snapshot_ttl_seconds=0`. The independently running 60-second status fragment uses that same data-only helper. After a successful transition, the route repeats the required current-week/recovery/pool reads and frozen-stat attachment that the old second run performed. Lock, week and injury safety transitions retain full reruns where necessary.

Runtime changes are confined to `weekly_ui.py`, version/build markers in `config.py`, and the import/reload prefix of `app.py`. The app body after `page_config()` is byte-identical. Four existing test adapters were updated for deliberate callback wiring/version changes; their protections remain. Two test/fixture files and release documentation/evidence were added.

All other original files are byte-identical: store methods, scoring, authentication, permission checks, provider retrieval, recovery, Commissioner dashboards, newsletters, AWTRIX, SQL, requirements and scheduled workflows. The existing performance changes from v1.0.10–v1.0.12 remain intact. Cache TTLs, 15-second live/lock display cadence, 60-second pregame status, two-/three-minute active refresh lanes and scheduled jobs are unchanged.

## Verification

The starting archive was `Teals_Sunday_Pickem_v1.0.12_FULL_CURRENT_APP.zip`, SHA-256 `f2bb3e99f3185578e5e9a56e45ef6fa086b602f423025e379a5f3f6d1cb2bb50`. All 302 original source files were verified against it; the baseline remained unchanged.

| Check | Result |
| --- | --- |
| Full release suite, Python 3.12.14 | **479 passed** |
| Full release suite, Python 3.13.16 | **479 passed** |
| New regression cases | **33** |
| Existing dependency warnings | 22 on each version |
| Outbound socket attempts in tests/traces | **0** |
| Compilation and release guard | Passed |
| Before/after whole-app scenario pairs | **185 matched** |
| Browser-bundle overlay | Byte-identical to full release |
| Documented rollback, Python 3.13.16 | **446 original tests passed** |

The warnings are the existing Supabase/PostgREST timeout and verify deprecations. The app’s dependency pins are unchanged: Streamlit 1.63.0, Supabase 2.31.0, pytest 8.4.2 and Requests 2.32.5. Python 3.13 matches the repository’s existing quality gate; 3.12 was also checked.

New coverage includes all five positions and single writes, confirmation/Edit freshness, Back and return destinations, unchanged Next, questionable/backup transitions, hidden and OUT starters, failed save/confirmation and explicit retry, account/login/token/mode/position/return/week/tab/lock changes, incomplete pools, obsolete callback generations, home recovery, isolated demo behavior, Review repair branches, a pool replacement during a successful save, and a backup becoming OUT before Next. Existing warm-deploy checks exercise the prior weekly UI generation and the new build marker.

## Actual before/after application measurements

Both sources ran as complete `app.py` applications through Streamlit AppTest with real application store methods. Only SQL transport and wall-clock dates were replaced. The anonymous fixture has eight accounts, seven archived weeks, 45 pool rows, saved starters/backups, hidden players and frozen season statistics. External sockets were blocked.

The ordinary account was compared across 44 scenarios. Three sequential before/after linked-owner samples each contained 47 scenarios, including revoking the synthetic owner mapping between interactions. That gives **185 scenario pairs**. Owner revocation removed Commissioner access while retaining normal player privileges in both versions; authorization still runs on every full page run.

Every pair matched for the final visible Streamlit element tree, widget order/labels/disabled states, own saved picks, builder mode/position and errors. The tree comparison removes runtime widget/form/fragment IDs and normalizes only the intended Build version label. Separate sessions were given the same already-shuffled card order; production shuffling was not modified. This is a server element-tree comparison, not a browser screenshot or pixel comparison.

Ordinary-account database operations are identical. Owner-account operations differ only by the owner-mapping read associated with an eliminated full run. The ordered remaining queries, selected fields and store-layer call frames match. Required post-write pool reads and home fresh-lineup reads remain.

The owner fixture waits an artificial **40 ms per database operation**. The times below are medians of three samples, include AppTest/instrumentation overhead, and are descriptive rather than pass/fail thresholds.

| Action | Before | After | Full runs | DB operations |
| --- | ---: | ---: | --- | --- |
| Build My Five | 0.248 s | **0.194 s** | 2 → 1 | 4 → 3 |
| Next, first saved pick | 0.285 s | **0.221 s** | 2 → 1 | 5 → 4 |
| Next, existing lineup | 0.257 s | **0.192 s** | 2 → 1 | 4 → 3 |
| Back | 0.165 s | **0.104 s** | 2 → 1 | 2 → 1 |
| Next, unchanged choice | 0.168 s | **0.105 s** | 2 → 1 | 2 → 1 |
| Save My Lineup | 0.380 s | **0.316 s** | 2 → 1 | 7 → 6 |
| Edit Lineup | 0.206 s | **0.147 s** | 2 → 1 | 3 → 2 |
| Starter tap, control | 0.121 s | 0.108 s | 1 → 1 | 1 → 1 |
| Warm Season, control | 0.099 s | 0.101 s | 1 → 1 | 1 → 1 |
| Expired-cache Live Sunday, control | 0.540 s | 0.553 s | 1 → 1 | 11 → 11 |

The controls retain their work and show ordinary timing variation. This release does not claim a speedup for already-one-run card taps, tab switches or live refreshes. In one existing-lineup Next sample, generated protobuf payloads fell from approximately 56 KB across two runs to 28 KB in one. Those bytes precede queue coalescing/compression and are **not measured network traffic**.

No production Supabase/ESPN latency, physical iPhone/Safari rendering, initial browser-token restoration or AWTRIX hardware was measured. The synthetic SQL adapter does not execute PostgreSQL constraints/triggers. Existing security/database tests remain, but this report does not claim an end-to-end production trial or an app-wide percentage speedup. The October 25 live slowdown remains unattributed; reducing the separate five-query public bundle or moving NFL work into the background requires a later scope.

## Packages, installation and rollback

`Teals_Sunday_Pickem_v1.0.13_FULL_CURRENT_APP.zip` is the complete source. `Teals_Sunday_Pickem_v1.0.13_GITHUB_BROWSER_UPLOAD.zip` contains only changed/new files under `UPLOAD_TO_GITHUB`, seven exact original files under `ROLLBACK_ONLY`, browser instructions, and package verification. Overlaying its upload files onto the exact v1.0.12 baseline reproduces the full v1.0.13 tree byte for byte; no upgrade deletion is needed.

`START_HERE.md` in the browser bundle gives the upload procedure, commit message and checks. Confirm the repository is on v1.0.12 before uploading. After normal deployment, verify Build 1.0.13 and perform the short phone smoke check described there. The running repository/version was not inspected or updated during preparation.

Rollback uses the merged pull request’s revert flow, or restores `ROLLBACK_ONLY` and deletes the two new test files. The documented manual rollback was constructed, all 302 originals matched byte for byte, and all 446 original tests passed on Python 3.13.16. Additional release evidence/documents may remain harmlessly. Saved database records, accounts and clock settings are not part of this file rollback.

`performance_evidence/v1_0_13` contains the final test logs/JUnit results, rollback results, raw before/after traces, comparator, offline test runner, package verifier and reproduction instructions. `SHA256SUMS_v1.0.13.txt` covers the current release files except itself. Older checksum/report files are retained historical records for their original releases.

No remote Git commit/tag, deployment, production database write or clock broadcast was performed. The approved release preparation is complete.
