# v1.0.12 — ESPN retrieval performance release

## Result and scope

The built-in ESPN provider now retrieves at most **three game summaries concurrently per refresh**. The calling thread still parses responses and merges them in the original eligible-game order, then performs the original scoring calculations and database writes. Each worker owns an independent session, retains the existing retry/timeout/fallback configuration, reuses its session for assigned games, and closes it before the refresh proceeds. The executor joins all workers before results are exposed.

Empty/single-game batches avoid an executor. Explicitly supplied sessions, custom provider subclasses, instance overrides and replaced sessions retain sequential compatibility and caller ownership. Worker sessions copy the caller’s headers and cookies into independent containers. A worker setup failure aborts before scoring writes; normal per-game provider failures retain the existing per-game preservation behavior.

Runtime files changed: `nfl_sources.py`, `nfl_sync.py`, `config.py` and the import/reload prefix of `app.py`. Two existing release-generation test adapters were updated. Two test/fixture files were added, along with documentation and offline evidence. The app’s UI body after `page_config()` is byte-identical to v1.0.11.

No application changes were made to `store.py`, `automation_recovery.py`, scoring formulas, authentication, permissions, player/Commissioner UI files, newsletters, AWTRIX code, SQL, dependency requirements or workflow schedules. The v1.0.10/v1.0.11 cache and transport improvements remain intact. The fresh post-provider pool reread and live-game timestamp comparison remain in place.

Version `1.0.12`; build `1.0.12-performance3`; proposed tag `v1.0.12`.

Commit message: `perf: release v1.0.12 with bounded concurrent ESPN summary retrieval`.

## Source and verification

The baseline was the exact uploaded `Teals_Sunday_Pickem_v1.0.11_FULL_CURRENT_APP.zip`, SHA-256 `4d78ae76980ec42a151a87d7aaf9a8511191036ef6b6fd790ff705569dbbfe1e`. All 279 original files were checked against that archive. The baseline remained unchanged.

| Check | v1.0.11 | v1.0.12 |
| --- | --- | --- |
| Full suite, Python 3.12.14 | 423 passed | **446 passed** |
| Full suite, Python 3.13.16 | 423 passed | **446 passed** |
| Existing dependency warnings | 22 | 22 |
| Unexpected outbound socket attempts | 0 | 0 |
| Python compilation | Passed | Passed |
| Release guard | Passed | Passed |

The quality gate requires Python 3.13; Python 3.12 was also validated to retain the previous release matrix. The unchanged warnings are Supabase/PostgREST timeout and verify deprecations. Tests ran in isolated environments using the app’s unchanged pinned requirements. Resolved dependencies and logs are included.

## New regression coverage: 23 cases

- Three requests deliberately held at once; a fourth waits. Results stay in input order even when completion differs, with no timing-threshold assertions.
- Full scoring comparisons against the sequential path with forced reverse and mixed response completion orders.
- Successful refresh, one-game timeout failure, all-game failure, malformed parsed content, temporarily missing player and endpoint fallback. Equivalent result objects, data rows, write order and request counts are compared.
- Exact QB/RB/WR/TE/K scoring; all hidden pool rows, saved picks and backup references remain.
- An actual post-provider `apply_pool_scores` reread honors a commissioner override entered while concurrent requests are blocked.
- Existing FINAL-game skipping, scheduled/ineligible/missing-ID filtering, and LIVE games with no pool players.
- Zero/one-job behavior, explicit custom sessions, subclasses, instance overrides, replaced sessions and duck-typed providers.
- Duplicate event requests and normalized-name collisions preserve the original merge behavior.
- Worker/session cleanup on success, request errors and worker setup failure; no remaining `pickem-espn` threads after return.
- The real Requests HTTP adapter with synthetic urllib3 transport verifies two retries on 503, 429 and read timeout before trying the next endpoint. The twelve-second connect/read timeout remains, and Retry-After values are passed to retry handling. Backoff waiting is suppressed only in tests.
- Unchanged adapter settings: retry total/connect/read = 2, backoff 0.35, GET only, status list 429/500/502/503/504, Retry-After respected.

The existing warm-deploy regression now also loads stale provider/scoring generations and confirms correct rebinding through automation recovery and the live UI. Existing cache, concurrent-reader, invalidation, failed-builder, explicit-fresh, current-week alias and commissioner-override regressions pass unchanged.

## Actual before/after application measurements

Both versions ran through the same offline harness in separate Python processes. The fixture contains ten LIVE games, 45 pool rows (20 hidden), eight synthetic participants, an empty lineup, saved starters/backups and historical results. One LIVE game has no pool players. Every synthetic HTTP attempt waits 60 milliseconds. Database methods are the real application methods over an in-memory query adapter. A fixed application clock makes output and freshness comparisons exact.

These measurements exercise the implemented application refresh, unlike the preliminary retrieval-only model used to approve the plan. Three samples were taken for each summary-refresh workload; the lightweight and busy-lease control scenarios were run once. Wall-clock timings are descriptive measurements, not test pass/fail thresholds.

| Scenario | Before | After | Provider requests | Logical DB operations before/after |
| --- | ---: | ---: | --- | ---: |
| Fantasy-stat refresh core | 0.620 s | **0.260 s** | 10 summaries | 10 / 10 |
| Active-user refresh, including lease and clock snapshot | 0.619 s | **0.261 s** | 10 summaries | 25 / 25 |
| Durable refresh core, including full scoreboard | 0.687 s | **0.319 s** | 1 scoreboard + 10 summaries | 14 / 14 |
| Lightweight game-state lane | 0.065 s | 0.065 s | 1 scoreboard | 20 / 20 |
| Active refresh with an occupied lease | Provider skipped | Provider skipped | 0 | 3 / 3 |

The maximum simultaneous summary requests changed from one to three. Request totals and database operations stayed equal. These counts exclude page authentication, full Streamlit rendering and the durable worker’s outer scheduler/other duties. They must not be confused with the previous audit’s 35-operation whole-render fixture.

Immediate warm public bundles perform **zero** database operations in both versions. The immediate next active check after a successful fantasy refresh makes no additional provider request. Successful leases are released; an occupied lease remains unclaimed. Cache hit/miss/invalidation aggregates, provider wait sums and spans, request counts, score age and game age are recorded in the raw results.

Across every scenario and every sample, before/after output fingerprints match for:

- Public bundles and saved lineup/backup references.
- Weekly standings, storylines, lineup reveal and Pulse output.
- Final-history archives, season standings and personal achievements.
- Newsletter text and complete AWTRIX snapshot payloads.
- Lock state, week score age and live-game age.

Full NFL ticker content includes the game without pool players. Unchanged LIVE clocks keep their older timestamp; completed refreshes retain the existing week-level freshness semantics. Authentication/session and permission protections are covered by the unchanged full regression suite; no real accounts were used.

## Freshness and failure behavior preserved

The live display stays at 15 seconds, pregame status at 60 seconds, lock checks at 15 seconds, active game-state refresh at two minutes, active fantasy-stat refresh at three minutes and durable Sunday scheduling at its existing five-minute cadence. Default public bundle TTL stays eight seconds. Failure cooldowns, refresh leases, recovery, finalization, publication and injury schedules are unchanged.

The same games are requested. FINAL games already captured are skipped; a failed game cannot overwrite prior scores with zero. When every summary fails, scoring writes and week freshness updates are withheld. The full scoreboard/fallback path in the durable refresh remains unchanged.

## Limits and remaining work

No production ESPN latency, Supabase latency, physical iPhone/Safari rendering or AWTRIX hardware was measured. The synthetic active-refresh reduction is about 58%; it is **not** a claim of 58% faster pages or a 58% faster app. New worker sessions incur real connection/TLS setup overhead that the synthetic HTTP delay does not separately model. Ordinary navigation without ESPN work may show no direct improvement.

The cap is per refresh, not a global limit across server processes or distinct refresh lanes. Existing lease overlap/expiry behavior was not redesigned. A twelve-second Requests timeout is not an overall refresh deadline: retries, fallback endpoints, slow response delivery and Retry-After can extend a refresh. Existing recovery policy is preserved. A provider-wide outage or very slow feed can therefore still cause a long wait.

The October 25 production slowdown has not been attributed conclusively. Remaining candidates include redundant render/database work, post-write data reuse, lease coordination and eventually separating NFL refresh work from page rendering. These were excluded from this approved release. The prior separate 19-page snapshot harness was not supplied; this report does not claim to rerun it or measure every page visually.

## Reproducibility and packaging

`performance_evidence/v1_0_12` contains raw before/after data, comparisons, complete baseline/release logs, JUnit output, resolved dependency versions, the network-blocking test runner and the measurement script. `tests/espn_performance_fixture.py` supplies the synthetic database/NFL fixture. Developer reproduction uses `measure_release.py SOURCE FIXTURE_DIRECTORY OUTPUT.json` in a fresh process for each source version. This is a developer validation command, not an installation instruction.

The full ZIP contains the complete application. `UPLOAD_TO_GITHUB` contains only additions/changes from the exact v1.0.11 source. The packaging check overlays those files onto that baseline and verifies byte-for-byte equivalence with the full release; no deletion is required for the upgrade.

The separate `ROLLBACK_ONLY` folder contains the six original modified files. Restoring these and removing the newly added concurrency test restores all original v1.0.11 files; extra evidence/documents and the unused fixture helper may remain. Rollback verification is included in the packaging report.

No remote Git commit or Git tag was created, no deployment was performed, no production data were mutated and no clock messages were broadcast. The commit message and tag above are ready for Michael’s normal browser-based installation workflow.

Final package validation: **119 Python files compiled; release guard passed; the documented rollback passed all 423 original tests on Python 3.13.16.** The small-bundle overlay matched the full release byte for byte.
