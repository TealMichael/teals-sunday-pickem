# Teal’s Sunday Pick’em v1.0.14 — release report

October 29, 2026 · version **1.0.14** · build **1.0.14-performance5** · proposed tag **v1.0.14**.

The approved release is implemented and validated for GitHub browser installation on top of v1.0.13. Normal populated standings bundles use four database reads instead of five. Opening, closing and switching an inline roster use one page run instead of two. No production deployment or remote repository change was performed.

## Changes

- `store.py`: request only the public `players(id,nickname,emoji)` relationship with the original lineup columns. Preserve default left-join semantics, empty lineups, null profiles and the existing flat bundle interface. Validate malformed responses and deduplicate profiles by ID. Preserve the original standalone pick query and its order, the hidden-inclusive pool, all games, backups and manual overrides.
- Only an `APIError` with `PGRST200` or `PGRST201` from the relationship read invokes the exact original loader. A populated fallback miss uses six operations including the failed attempt. There is no permanent capability flag. Other errors propagate through the original cache failure path; failures in later reads never invoke relationship fallback.
- `gate4_ui.py`: the same buttons call a session-state-only roster toggle before the normal page/fragment run. It captures only a player ID and makes no database or permission decisions. Existing authenticated routing and roster privacy rendering remain. No-detail buttons stay inert. Reaction and structural phase reruns remain unchanged.
- `config.py` and the reload prefix in `app.py`: new build identity, store schema 9 and Gate 4 UI schema 13. Weekly UI is rebound after Gate 4 reloads so warm workers use the new functions.

Only these four runtime files changed. Four existing test/fixture files were adapted to the new response shape, counts and callback contract; four test/fixture files were added. All 342 baseline files are retained. The public cache coordinator and every other store method are byte-identical. All other Gate 4 functions, the app body after `page_config()`, SQL, provider code, dependency pins, scoring, auth, commissioner logic, newsletters and AWTRIX files are unchanged.

The rejected three-query nested-picks experiment is not included in the runtime. The release retains pick order because regrouping can reorder equal-name/equal-count lineup-reveal entries.

## Validation

| Check | Result |
| --- | --- |
| Complete suite, Python 3.12.14 | 555 passed; zero outbound socket attempts |
| Complete suite, Python 3.13.16 | 555 passed; zero outbound socket attempts |
| New regression cases | 76, added to the prior 479 |
| Actual-source complete-app comparisons | 76 scenario pairs; screens, controls, saved picks, modes, errors, reactions and write counts match |
| Actual-source downstream consumers | 12 fingerprints × 36 scenario pairs match |
| Equal-name/count ordering | All 30 permutations preserve exact pick order and consumer output |
| Warm deployment | Old v1.0.13 store/Gate 4 functions reload; Weekly UI references rebind |
| Rollback | All 342 original files restored exactly; 479 original tests pass on Python 3.13.16 |
| Packaging | Browser overlay matches full source byte for byte; compilation and release guard pass |

The 36 warnings in each release suite are SDK timeout/verify deprecations: the original suite emitted 22, and seven new mocked SDK cases exercise the same two warnings again. They are not test failures. Versioned logs/XML and the exact dependency resolutions are included.

Tests cover single-flight sharing for eight readers, per-week isolation, returned-copy isolation, expiry, fresh reads during a normal load, invalidation during a read, error wakeups/retry at each read stage, independent fresh clock/archive reads, missing/malformed profiles, narrow relationship fallback, full-game coverage and private field projection. The real installed Supabase/PostgREST SDK runs against `httpx.MockTransport` for selection, filter, schema, timeout and error parsing checks.

The complete-app fixtures cover 15 participants, empty and partial lineups, hidden starters, activated backups, manual overrides, LIVE/PROVISIONAL/FINAL, reactions and Season navigation. Additional paired runs change the account, phase or week after a click and before rendering. UI unit tests cover logout, removed rows, inactive-backup privacy, activated-backup display and no-detail mode.

Consumer comparisons include the bundle, weekly standings, storylines, recap, lineup reveal, clock payload, final archive, season standings, achievements, newsletter, Pulse and saved picks. Only the unordered profile collection is normalized by ID. Pick order and visible outputs remain exact.

## Performance evidence

Three paired samples use **40 ms of artificial wait per database operation**, a linked-owner account and the complete Streamlit app. Times include AppTest/instrumentation overhead and are descriptive, not performance thresholds or production predictions.

| Interaction | v1.0.13 median | v1.0.14 median | Database operations | Full page runs |
| --- | ---: | ---: | ---: | ---: |
| Cache-expired Live Sunday | 0.550 s | 0.506 s | 11 → 10 | 1 → 1 |
| Open your roster | 0.309 s | 0.205 s | 5 → 3 | 2 → 1 |
| Close your roster | 0.307 s | 0.203 s | 5 → 3 | 2 → 1 |
| Open another roster | 0.308 s | 0.200 s | 5 → 3 | 2 → 1 |
| Switch to another roster | 0.315 s | 0.205 s | 5 → 3 | 2 → 1 |
| First view after a manual override | 0.467 s | 0.417 s | 9 → 8 | 1 → 1 |
| Warm Live Sunday control | 0.201 s | 0.206 s | 3 → 3 | 1 → 1 |

The standalone cold bundle median was **0.205 → 0.164 seconds**, with five → four reads. Warm controls do no less work; small timing differences there are noise.

One due-refresh pair used 40 ms database waits and 60 ms ESPN request waits. Database operations fell **36 → 34**, saving one read in the fresh clock snapshot and one in the page bundle. Both issued ten ESPN summary requests with peak concurrency three, produced identical pool scores, week freshness and clock output, closed worker sessions, and made no additional provider request on the immediate warm view. Sample time was 2.472 → 2.380 seconds; one pair is not a latency guarantee.

## Scope and limits

This is a performance-only release. The eight-second public cache, invalidation generations, failure propagation, fresh-read bypass, 15-second live display, two-minute game-state lane, three-minute player-stat lane and existing scheduled backend all remain unchanged. It does not trade freshness for speed.

Production PostgreSQL joins/query plans, the deployed Supabase relationship cache, real ESPN latency, physical iPhone rendering and AWTRIX hardware were not measured. SQL relationships are modeled; SDK requests are real SDK code against an in-memory HTTP transport. AppTest compares server element trees with runtime IDs and the intentional Build label normalized, not browser pixels.

A session elected to refresh scores still waits synchronously on ESPN. This release reduces ordinary work; it cannot guarantee that every Sunday pause is resolved. Moving provider work out of page serving would require a separate approved design.

## Installation and recovery

Use `START_HERE_v1.0.14.md` in the full source, or `START_HERE.md` in the browser-upload ZIP. Install after v1.0.13, confirm Build 1.0.14, and check remembered login, Commissioner access, saved starters/backups, roster open/close/switch and the normal live freshness display. The running deployment was not inspected or modified.

Commit message: `perf: streamline live standings reads and roster taps in v1.0.14`.

The browser ZIP includes exact original replacement files in `ROLLBACK_ONLY`. Delete the four new test/fixture files before a manual rollback; the instructions list them. Extra evidence/documents may remain. No database restoration is needed.

Starting archive: `Teals_Sunday_Pickem_v1.0.13_FULL_CURRENT_APP.zip`; SHA-256 `0bcc45369873b82bd049c7709f5e35e6099c1027edd8b4110b02376e293d2022`.

For reproducible traces and commands, see `performance_evidence/v1_0_14/README.md`. Package verification is included outside the upload directory in the browser ZIP.
