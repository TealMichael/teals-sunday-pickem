# v1.0.10 — Test and Performance Report

Prepared October 27, 2026 for the approved R1–R4 performance release.

## Provenance and scope

- Base archive: `Teals_Sunday_Pickem_v1.0.9_FULL_CURRENT_APP.zip`.
- Base SHA-256: `1bcb92466292fd92ab1417739db5c95689f7353eb53430547bf9123f1adeedaa`.
- Release: `APP_VERSION = "1.0.10"`; build `1.0.10-performance1`; proposed tag `v1.0.10`.
- Exactly seven runtime files changed: `app.py`, `config.py`, `store.py`, `player_season_stats.py`, `weekly_ui.py`, `gate5.py`, `gate5_ui.py`.
- Three existing test adapters changed; two test files containing 26 new cases were added. No tests or application features were deleted.
- All 260 other original files remain byte-identical, including scoring logic, authentication/commissioner authorization, NFL synchronization, workflow schedules, SQL, clock logic/script, newsletter generation, social logic and CSS.
- The three additional release documents are this report, the release handoff and the machine-readable performance summary.

## Complete-suite results

| Check | Result |
| --- | --- |
| Original v1.0.9 baseline | **386 passed** in 4.34 seconds on Python 3.12.14, recorded during the audit |
| Updated full suite, Python 3.12.14 | **412 passed**, 22 dependency deprecation warnings, in 5.13 seconds |
| Updated full suite, Python 3.13.16 | **412 passed**, 22 dependency deprecation warnings, in 7.25 seconds |
| Python source compilation | **114 files passed** under Python 3.13 |
| `release_guard.py` | **PASS** |
| Outbound connections during the suite/probes | Blocked; **zero attempts** recorded |
| Original source integrity | Original extracted upload retained unchanged |
| Upload overlay/package check | The 15-file browser update applied to the original project reproduces the complete 275-file release byte for byte |

The two suite runtimes are test-run durations, not application speed benchmarks. The 22 warnings arise from deprecated timeout/verify argument handling in the pinned Supabase/PostgREST libraries, including the deliberate legacy-route comparison. Their behavior was preserved; no dependency upgrade was introduced.

Direct dependencies remain unchanged: Streamlit 1.63.0, Supabase 2.31.0, requests 2.32.5 and pytest 8.4.2. PostgREST 2.31.0 and HTTPX 0.28.1 were present in both validation environments. Python 3.13 matches the repository's configured GitHub quality-gate major/minor version.

## New regression coverage

The six transport cases use the actual installed Supabase/PostgREST/HTTPX request builders with an in-memory HTTP transport. They execute synthetic requests without contacting a server.

| Area | Regression checks and outcome |
| --- | --- |
| Transport lifetime and concurrency | 100 requests across eight threads use one initialized HTTP client; each response matches its own filter. **PASS** |
| Request equivalence | GET, INSERT, UPSERT, PATCH and DELETE match the original route's method, URL/query, body, schema/auth/other functional headers and timeout. **PASS** |
| Client options and query isolation | Eight-second connect/read/write/pool timeout preserved; token auto-refresh and persistence remain disabled; fresh builders do not inherit earlier filters or conflict parameters. **PASS** |
| Frozen-value reuse | Sixteen concurrent readers share one completed metadata read. Returned values and nested attached card stats are independent copies. **PASS** |
| Uncacheable values | Missing, failed, empty, wrong-schema, wrong-week and malformed-player snapshots remain uncached. **PASS** |
| Isolation | Season/week/schema keys remain separate. Commissioner-owner/device and reaction keys cannot enter this cache. **PASS** |
| Invalidation | Confirmed writes invalidate only the relevant frozen key; unrelated writes preserve it; rejected writes preserve the last confirmed value. An in-flight old read cannot leave a stale cache after the write returns. **PASS** |
| Retry and eligibility | Existing failure-marker cooldown remains effective; another worker's first completed snapshot can be observed; transient read errors are retried later; demo/unpublished weeks still skip snapshot loading. **PASS** |
| Pregame reuse | Actual Streamlit home rendering obtains one fresh joined lineup read. Immediate subsequent rendering still refreshes status. **PASS** |
| Recovery and hidden selections | Each status invocation reads after recovery, reflects changed selections, and resolves preserved hidden starters. **PASS** |
| Lock transition | Locked status requests the existing full rerun before reading/editing lineup content. **PASS** |
| Corrections | One pool read per ordinary render; existing controls and pre-lock score restrictions retained. **PASS** |
| Failed correction | A simulated partially failed pool mutation triggers a fresh read before the score-control options are displayed. **PASS** |
| Preview/action separation | Reused preview equals fresh preview; explicit empty context still rejects a missing outgoing player; post-lock mutation remains rejected. **PASS** |
| Warm deployment | Simulated old module/build markers cause the new dependencies to reload before UI functions are bound, in an isolated subprocess. **PASS** |

The legacy `.schema()` route duplicates `X-Client-Info`; the new route sends the normal single library-identification value. That nonfunctional identification-header difference is explicitly allowed in the comparison. All other HTTP headers must match. No authentication header was excluded.

The original 386 tests still run, including authentication, unified commissioner access, PIN throttling, lineup rules and backups, hidden selections, provider/scoring protections, weekly/season results, automation, clock schedules/melodies, newsletter, Pulse and existing layout contracts. Three existing adapters were updated because they previously required per-query schema construction or a fragment with no return value; their underlying schema and display-order guarantees remain asserted.

## Before-and-after measurements

Fixture: 12 synthetic participants, 50 current pool rows, 10 synthetic games, 72 archived result rows, and a prior-week pool. These values do not describe actual users or the October 25 NFL slate. Counts exclude the outer authentication shell, SQL-internal trigger work and network retries.

Cold means empty application caches/new test session. Immediate warm means a subsequent render before TTL expiry. Completed frozen picker statistics already exist in the measured picker fixture; the new cache fills on its first validated read. A newly generated snapshot can still require its first later read before becoming cached.

| Scenario | v1.0.9 cold / warm | v1.0.10 cold / warm |
| --- | --- | --- |
| Fresh live Sunday | 12 / 2 operations | 12 / 2 operations |
| Pregame home | 6 / 1 reads | **5 / 1 reads** |
| Picker | 4 / 1 reads | **4 / 0 reads** |
| Season | 3 / 0 reads | 3 / 0 reads |
| History | 2 / 0 reads | 2 / 0 reads |
| Profile | 3 / 0 reads | 3 / 0 reads |
| Commissioner Home | 7 / 5 reads | 7 / 5 reads |
| Commissioner Week | 5 / 3 reads | 5 / 3 reads |
| Commissioner Players | 5 / 3 reads | 5 / 3 reads |
| Commissioner Corrections | 9 / 8 reads | **7 / 6 reads** |
| Commissioner Newsletter | 6 / 4 reads | 6 / 4 reads |
| Commissioner Clock | 7 / 6 reads | 7 / 6 reads |
| Commissioner Diagnostics | 6 / 4 reads | 6 / 4 reads |
| Fantasy-stat refresh-winning render | 35 / 2 operations | 35 / 2 operations |
| Game-state refresh-winning render | 30 / 3 operations | 30 / 3 operations |

| Interaction | v1.0.9 | v1.0.10 |
| --- | --- | --- |
| Player-card tap | 1 read; 0 writes; 1 script execution | **0 reads**; 0 writes; 1 execution |
| Next, changed existing pick | 3 reads + 1 write; 2 script executions | **1 read + 1 write**; 2 executions |
| Simulated live tick at 15 seconds | 7 reads | 7 reads |
| Simulated live tick at 30 seconds | 9 reads | 9 reads |
| Successful remembered login | 2 reads + 3 writes | Unchanged |
| Successful remembered restoration | 2 reads + 2 writes | Unchanged |
| Successful linked commissioner authorization chain | 5 reads | Unchanged |

The 35-operation refresh fixture calls ten stubbed ESPN summaries; the 30-operation fixture calls one stubbed scoreboard method. These paths and provider-call counts remain unchanged. The first release improves their database transport reuse without changing the refresh schedule or removing provider waits.

### Transport construction measurement

| Measurement, 100 preparations per version | v1.0.9 | v1.0.10 |
| --- | ---: | ---: |
| New HTTP clients after initial transport setup | **100** | **0** |
| Median table-query preparation | 0.484 ms | 0.0071 ms |
| 95th percentile | 0.687 ms | 0.0155 ms |

These timings measure local query-builder/client construction only, without making HTTP requests. They demonstrate removed work but cannot establish a page-speed percentage or quantify actual TCP/TLS savings. A separate regression executes 100 mock HTTP requests through the one shared client to check thread/query isolation.

## Behavioral comparisons

Before/after runs used the original v1.0.9 and new release in separate processes with the same fixture, frozen application time and controlled test-only card shuffle. Production card randomization was not changed. Streamlit's internal temporary widget/form IDs were excluded from the display comparison.

- **19 page/interaction/tick snapshots matched** in content, control configuration and order, allowing only `Build 1.0.9` to become `Build 1.0.10` on Profile.
- Synthetic saved table state matched after card selection and after Next.
- Weekly leaderboard, storylines, season standings and personal season story/achievement outputs matched exactly.
- Generated AWTRIX snapshot and Tuesday newsletter text matched exactly for the fixture.
- Authentication probe success assertions and database-operation counts matched the audit baseline.

No changes were made to the 15-second live display interval; two-/three-minute active refresh lanes; five-minute durable refresh; Tuesday publication; Monday finalization; injury schedules; clock polling/rotation/ACKs; or lineup and injury protections.

## Limits and remaining production checks

No real Supabase credentials, production rows, ESPN/nflverse/Sleeper requests, commissioner mutations or broadcasts were used. SQL migrations, RLS, database triggers, real network latency, multi-process deployment behavior and actual AWTRIX hardware were not exercised against production. Existing SQL and clock files are unchanged.

Streamlit AppTest verifies generated UI elements and interactions, not Safari/iPhone paint, scrolling, browser storage restoration or physical device responsiveness. The fragment comparison invokes the original fragment function with controlled cache-clock progression; it is not a real browser timer test. The fake PostgREST boundary does not enforce production constraints or row caps. Some existing regressions assert source contracts rather than live integration.

Frozen successful card snapshots are already immutable in the existing application workflow. Local confirmed writes invalidate their cached copy. Direct out-of-band SQL edits to an already-frozen snapshot are not an existing supported refresh path; a worker restart clears its process cache if such a manual repair is performed.

The first release leaves synchronous refresh-winning waits and general live-bundle cache-miss duplication intact. Validate real iPhone responsiveness and unchanged score freshness after the user's normal installation, especially during a live slate. Do not run production reset/regenerate/finalize operations merely to test speed.

## Reproduction and artifacts

The repository retains its normal `pytest -q`, Python compilation and `python release_guard.py` checks. New regression files are `tests/test_v110_transport_and_snapshots.py` and `tests/test_v110_render_reuse.py`; they require only the unchanged application dependencies. The accompanying `V1_0_10_PERFORMANCE_RESULTS.json` preserves the measured counts, equality checks, transport metrics and source/environment verification.

Both release archives were integrity-checked, and applying only the browser upload payload to the exact original upload was compared against every file in the full release. No deploy, remote commit or tag creation was performed.
