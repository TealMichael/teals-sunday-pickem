# v1.0.7 Hotfix 7.14.1 — Pre-Sunday Safety Audit and Guardrails

## Scope of review

Audited the reconstructed Hotfix 7.14 application against the exact 7.14 GitHub upload ZIP. Traced the Tuesday publication, injury/schedule replacements, saved-pick guards, Sunday lock, five-minute GitHub worker, two-speed active live engine, AWTRIX game-state consumption, post-lock lineup reveal / personalized race, Monday final archive, and profile achievements. Inspected database migration guards and deployed workflow files. This was a local code and simulated-provider audit; **the actual deployed GitHub commit, private Supabase data, and physical AWTRIX clock were not accessed**.

## Confirmed bugs, now guarded

1. **ESPN game-state regression:** A lagging/incomplete scoreboard could replace an already confirmed FINAL 27–17 game with SCHEDULED 0–0, or push a LIVE game back to SCHEDULED. `refresh_live_game_state` now keeps a prior FINAL state if the new response is not final, and a prior LIVE state if the scoreboard reports SCHEDULED. Normal live/final score advances still update.
2. **Lagging durable schedule:** In `sync_schedule(prefer_live=True)`, nflverse could report SCHEDULED after ESPN had confirmed LIVE; the old rule preserved live state only if *both* feeds said LIVE. It now preserves LIVE against SCHEDULED, keeping scoring and the ticker from going backwards.
3. **Misleading stale game clock:** `upsert_nfl_games` used to reset `provider_updated_at` on every successful poll, even when the upstream LIVE clock and scores were identical. Thus repeated stale `Q2 0:00` responses could look fresh indefinitely and defeat the seven-minute stale-clock guard. The DB upsert now reuses the original game-state timestamp for unchanged LIVE score/quarter/clock and advances it only after a real state change. This costs at most one additional shared Supabase read per live upsert; it does not add NFL provider requests. On an incidental DB read failure, scoring still writes normally.
4. **Partial schedule could destabilize the pool:** `reconcile_pool_schedule` previously treated a team missing from a partial schedule as ineligible and began mutating pool rows before possibly failing on replacement shortages. Now it refuses an incomplete feed *before any pool-row write*, preserving the published pool and all saved picks for retry or Commissioner review. A real changed kickoff for teams still present remains eligible for the normal replacement logic.

## Stable areas confirmed

- Season stats, 1 PM reveal, personal Sunday race, and profile achievements/season story are read-only presentations; they do not call lineup-saving or pool-publishing operations.
- Published pool cannot be republished; the background injury/schedule/Commissioner swap paths preserve already-saved starter IDs. A valid backup may activate according to existing rules. The server and database lock still govern editing at 1 PM ET.
- Weekly archived results drive achievements, not Sunday provisional scoring. Archive player IDs are stable across nickname changes.
- Five-minute GitHub worker, two-/three-minute active lanes and fifteen-second app/clock reads are unchanged.
- Prior-week roster cleanup only targets finalized weeks older than the published one.

## Verification and boundaries

Added seven simulated regression tests for incomplete schedules, stalled clocks, scoreboard state regression, and schedule-feed regression. The four newly introduced hazard tests failed before the fix and pass afterward. The **full local test suite passes: 313 passed**, all Python modules compile, and `release_guard.py` passes. The current package was also validated against the same exact local files included in Hotfix 7.14's prior upload package. No production ESPN/Sleeper/nflverse calls or live Supabase writes were made.

**Remaining external risks:** provider outages/partial player statistics, delayed GitHub scheduling, and real account/clock behavior cannot be guaranteed by local tests. Monitor Commissioner → Diagnostics during the Sunday pre-lock period and after kickoff. A green GitHub job indicates the script ran; inspect the inner injury/live run outcome if data looks stale. Do not manually republish an already-published week.

## Installation

Install over **Hotfix 7.14**. Extract ZIP; open `UPLOAD_TO_GITHUB`; upload its *contents* to repository root on `main` (preserve the `tests/` directory), replace matching files, and wait for Quality Gate + Streamlit redeploy. No Supabase SQL, AWTRIX reinstall, or `.github` workflow replacement. This is a focused guardrail update, not a new feature release.

**Exact commit:** `v1.0.7 hotfix — harden Sunday game feeds and pool safety`

**Exact tag:** `v1.0.7-hotfix7.14.1`
