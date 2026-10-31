# v1.0.15 background refresh — verification report

October 31, 2026. Built against the exact v1.0.14 full-source ZIP (SHA-256 `bb2de5687d5e2b42c0f0016e31216ef75d1b7980b6144018375e572dd082f794`); all 398 extracted baseline files verified byte-for-byte.

## Result

The release is prepared for a coordinated database-first installation. **No deployment or production database change was made.** Use `START_HERE_v115.md`; uploading Python files alone is insufficient. Package integrity and the exact browser-overlay comparison are recorded in `Pickem_v115_Package_Verification.json`.

Live Sunday now submits bounded background work and renders saved data without waiting for ESPN. Shared PostgreSQL ownership and transaction checks reject late/expired candidates, protect current manual corrections, and prevent old direct score writers from bypassing the protocol. The only additional player-facing UI is the small update/delay caption above Standings. Normal rules, navigation, scoring, five-player picks, backups, lock behavior, login/PINs, commissioner access, newsletters, history and AWTRIX consumers are retained.

The installation begins with background mode off. Its supported synchronous fallback retains the new safety checks. An emergency full-code rollback is supplied separately and requires replacing the app with the maintenance page and stopping jobs first.

## Acceptance evidence

| Gate | Python 3.12.14 | Python 3.13.16 |
| --- | ---: | ---: |
| Unchanged v1.0.14 baseline suite, recorded by the preceding pass | 555 passed | 555 passed |
| Current release regression suite | 556 passed | 556 passed |
| Real PostgreSQL/native integration suite | 89 passed | 89 passed |
| Paired whole-app scenarios | 70 matched | 70 matched |

No failures or skips in these reports. The release keeps all 555 existing regression cases, adapts five test files for new version markers/protected routing, and adds one SDK transport-isolation test. The existing transport semantics tests use an unprotected table where direct routing remains appropriate; a separate new test checks protected RPC payloads/schema headers and independent clients. The original baseline suite and source remain available in the evidence package.

The 89 integration cases execute the real migrations and functions on disposable PostgreSQL 16.15 using the application’s actual store/scoring methods. Test-only transport maps SDK operations to SQL; an installed-SDK MockTransport test separately verifies the HTTP RPC shape. Synthetic provider fixtures are used throughout.

### Database and refresh safety

- Eight independent processes compete for one week; exactly one owner wins. Ownership survives claimant exit until expiry; a later claimant gets a newer generation. Expired/wrong/duplicate candidates cannot change data or the current owner’s outcome.
- Expiry during a multi-row commit and an invalid row after valid rows roll back the entire transaction. Unexpected errors and database claim/commit failures do not publish a partial scoring candidate.
- Anonymous/authenticated callers cannot use the mutating RPCs. Functions use an explicit safe search path; coordinator tables are not directly writable by the server role. Legacy direct score writes are rejected at the database boundary.
- Manual set/clear corrections use current raw points; concurrent correction/archive/clock tests preserve current values and reject stale derived snapshots. Pool edits invalidate in-flight work; locked picks and late replacements stay protected.
- Background admission is bounded to one process-owned thread, with no queue per phone. Start failure, status-read failure, cache notification failure, local invalidation, cross-host cache expiry and nonblocking shutdown are exercised.
- Provider sessions use the existing request timeouts/retry policy and close after coordinated work. Scoring ownership has an absolute 240-second expiry; other coordinated operations have 420 seconds, with no renewal path. A permanently stuck thread can occupy its one slot until process restart, but cannot retain database write authority indefinitely.

### Preserved outputs and app behavior

Twenty-one pipeline scenarios compare original/new scoring, saved tables, provider-call counts and consumers: stats/game/durable lanes across success, one/all summary timeouts, malformed data, missing players, final games and scoreboard fallback. Comparisons include standings, storylines, recap, lineup reveal, season history, personal achievements, newsletter, pulse and clock payloads. Failed scoring cannot advance score-success freshness; game-only success cannot hide a scoring failure.

The 70 paired app scenarios cover 47 pre-lock/navigation cases, 17 live/results cases and six account/week/phase transitions. Visible server-rendered element trees, picks/reactions and writes match after normalizing runtime widget IDs and build labels. Paired fixtures use synthetic transport; native protocol behavior is covered separately.

Native tests render the real Live Sunday screen against PostgreSQL while deliberately holding provider responses, then tap a roster before releasing the response. Both provider success and failure preserve responsive interactions; captions change truthfully afterward. Whole-app PIN login, linked commissioner unlock and every commissioner section render against the native database harness. Remembered-session creation/restoration/revocation, invalid PIN/token rejection, manual refresh/correction audit records, publication, roster purge, final results, archive retry, next-week shell recovery and demo diagnostic restoration are also checked.

### Timing and cadence

The recorded final Python 3.13 native UI samples are in `native_ui_success.json` and `native_ui_failed.json`. These are local server-side render times with synthetic provider waiting, not networked iPhone measurements. No percentage speedup is claimed. The decisive check is that cold/warm rendering and a roster tap complete while the provider is still held.

The original 15-second display tick, eight-second bundle cache, approximately three-minute active stats target, two-minute full-scoreboard target, failure cooldowns, workflow schedule and provider concurrency remain. The scheduled SQL guard was corrected during this pass to match the existing five-minute **start-to-start** policy and its 30-second dispatch tolerance; boundary tests cover both sides. Full-scoreboard lane fairness is checked separately from fantasy-score freshness.

### Installation and rollback

Migration application/reapplication, old-writer rejection, mode enable/disable, synchronous refresh, full v1.0.14 rollback with preserved data, and migration reinstallation are tested in the disposable database. Delivered operational SQL is executed by the tests. The rollback rejects new-protocol claims before permitting original writers again. The file-overlay audit proves that applying the browser package to v1.0.14 yields the full-current package byte-for-byte; its reverse overlay restores all original modified files.

## Limits

- This is local PostgreSQL and server-side Streamlit AppTest validation, not a hosted Supabase/PostgREST staging deployment, browser pixel comparison or physical iPhone test. The installed app still needs the short smoke check in the guide.
- ESPN/Sleeper/nflverse production responses were not requested. Real-provider outages, managed-host uptime and GitHub dispatch delays remain external conditions.
- Background threads belong to the app process. They continue without a particular phone request, but cannot survive host death. Closed-browser scheduled recovery and app-restart ownership recovery were simulated/tested separately; no continuous fast-update guarantee is made during host downtime.
- Existing SDK deprecation warnings are recorded; tests pass. The package does not change dependency versions or the scheduled workflow.
- Older prototype reports and historical release notes are included for provenance; this report, the current JUnit files, and the package verification JSON describe this release.
