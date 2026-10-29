# v1.0.11 — Complete Test and Performance Report

## Source and boundaries

- Base: `Teals_Sunday_Pickem_v1.0.10_FULL_CURRENT_APP.zip`, verified as `APP_VERSION = "1.0.10"` and `APP_BUILD_VERSION = "1.0.10-performance1"`.
- Release: `APP_VERSION = "1.0.11"`, `APP_BUILD_VERSION = "1.0.11-performance2"`.
- Runtime edits limited to `store.py`, `clock_broadcast.py`, `gate4_results.py`, `config.py` and `app.py`.
- Two existing test adapters were updated for the new build marker and explicit-fresh method signature; one regression file with **11 tests** was added.
- No SQL, dependency, secret, workflow schedule, scoring algorithm, UI layout or AWTRIX script change.

## Validation in this isolated environment

| Check | v1.0.10 baseline | v1.0.11 release |
| --- | --- | --- |
| Python 3.12.14 full suite | 412 passed, 22 warnings | **423 passed, 22 warnings** |
| Python 3.13.16 full suite | 412 passed, 22 warnings | **423 passed, 22 warnings** |
| Python 3.13 source compilation | Existing source compiled | **115 files compiled** |
| `release_guard.py` | Prior report states PASS | **PASS** |
| New concurrent/freshness cases | Not present | **11 passed** |

Warnings remain the existing pinned Supabase/PostgREST timeout/verify deprecations. Current dependencies were installed unchanged into isolated temporary test directories. There were no production secrets or live network operations in tests; real backend/provider interactions were represented by in-memory fakes and synthetic fixtures.

## New deterministic concurrency coverage

1. Eight concurrent cold readers of one populated public bundle produce one five-query build; each returns an equal, independent nested value.
2. A failed in-flight builder wakes all waiters and permits a later successful read; partial results are not cached.
3. Invalidation during a paused read cannot repopulate an old bundle, whether invalidation is week-specific or global.
4. A slow bundle for one week does not block a different week's bundle.
5. A short TTL argument retains its old semantics; explicit `fresh=True` bypasses an existing eight-second cache entry.
6. An explicit fresh read interrupted by invalidation retries against the new generation.
7. A confirmed week status update invalidates the current-week alias; a paused alias read cannot restore obsolete data.
8. Clock and archive consumers use explicit fresh reads without changing their empty-fixture output.
9. `apply_pool_scores` still rereads the pool after provider waiting, preserving a commissioner's intervening manual score override.

The event/barrier probes use synchronization events and bounded deadlock safeguards, not elapsed-time performance assertions.

## Operation counts and interpretation

The original release used five SQL requests per cold populated bundle: `lineups`, `lineup_picks`, `players`, the entire `player_pool` and `nfl_games`. The v1.0.10 forced eight-reader probe was independently reproduced as **40 operations**. The new deterministic test confirms eight readers sharing one new generation perform **5 operations**, a 35-operation reduction in that synthetic same-process burst. One cold reader remains at five operations and an immediate warm reader remains at zero. No query shapes or TTL durations changed.

A fresh authoritative read performs five operations even if the ordinary eight-second cache is populated. Clock and Monday archive data may therefore require additional queries for correctness. This release does not remove the 35-operation heavy refresh-winning path, its stubbed ESPN summaries, the 15-second live display cadence or physical iPhone rendering time.

## Existing functional protections retained

The unchanged original tests cover unified commissioner/player authentication, PIN hashing and throttling, remembered sessions, five starters/backups, hidden preserved pool rows, Sunday 1 PM ET locks, injury/frozen kickoff rules, commissioner tools, score overrides, standings and history, Pulse/reactions, newsletter output, Monday finalization and Tuesday publication, GitHub and Streamlit recovery cadence, and AWTRIX snapshot/rich-ticker/ACK/melody contracts. New clock/archive fresh-read tests specifically cover the altered call signature, and the post-provider override test exercises a paused provider scenario.

## Limits and future work

The original full v1.0.9 performance audit and its standalone evidence/probes were not in the attached v1.0.10 archive; the present source and v1.0.10 release report/results were available. The prior 19 UI screenshot/snapshot fixture harness was not supplied as a reproducible standalone artifact, so this report does **not** claim to have rerun those exact 19 comparisons. Instead, the unchanged existing functional suite was run on both the provided baseline and release source, and new deterministic data-path comparisons were added.

No production Supabase latency, real ESPN latency, Safari/iPhone rendering, cross-process deployment behavior, SQL trigger execution against a production database, or actual AWTRIX hardware was measured. The October 25 incident cause remains unverified. Future changes to refresh leases, post-write context reuse, nested PostgREST queries and ESPN concurrency need separate scope and tests.

No production data were mutated, clock messages broadcast, GitHub files changed or deployment performed.
