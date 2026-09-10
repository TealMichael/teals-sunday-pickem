# Release Handoff — v1.0.6 Automation Hardening

Baseline: **v1.0.5 — Tap-to-Edit Lineup Review**.

## Purpose
GitHub Actions remains the primary scheduler, but the Week 1 rehearsal showed scheduled runs can start hours late. v1.0.6 adds a stale-only server fallback so the critical Sunday experience is no longer dependent on GitHub firing on time.

## Runtime changes
- `automation_recovery.py` — new critical-window recovery coordinator.
- `store.py` — latest-run lookup + server-only refresh lease helpers.
- `weekly_ui.py` — Sunday-tab recovery hook only; ordinary fresh page views use the already-loaded week freshness stamp.
- `gate5_ui.py` — Commissioner Week screen shows whether the fallback lease is armed and the latest recovery event.
- `config.py` — APP_VERSION 1.0.6.
- `db/005_automation_hardening.sql` — server-only lease table.
- `release_guard.py` + regression tests/docs.

## Recovery windows
- Tuesday publication: first active Sunday-tab session may recover if the pool is still unpublished 10 minutes after opening.
- Sunday final two hours before lock: overdue injury/status refresh can recover after the normal 15-minute interval + 2-minute grace.
- Sunday 1 PM ET through the 12-hour live window: overdue live scoring can recover after the same 17-minute threshold.
- Monday finalization: active session may recover after the 9 AM target + 20-minute grace.
- Provider failures are throttled for five minutes before another fallback attempt.

## Concurrency / safety
`pickem.refresh_leases` has a primary-key lease name. Expired leases are removed, then only one service-role insert can win. Other simultaneous sessions simply render the existing stored data. The fallback is non-fatal: if the lease table is unavailable or a provider call fails, the player app keeps working and GitHub/manual Commissioner controls remain available.

A recovered Monday finalization also creates the next real-week shell, matching the existing `run_auto` bookkeeping so Tuesday opening cannot be stranded.

## Protected code
Byte comparison against v1.0.5 confirms no changes to:
- `nfl_sync.py`
- `nfl_sources.py`
- `nfl_scoring.py`
- `nfl_rankings.py`
- `live_dress_rehearsal.py`
- `auth.py`
- `security.py`
- `.github/workflows/nfl-refresh.yml`
- `.github/workflows/quality-gate.yml`

## Verification
- pytest: **179/179 PASS**
- Full Week Rehearsal: **9/9 PASS**
- compileall: **PASS**
- release_guard: **PASS**

## Install
1. Upload the GitHub patch to `main` and wait for the Quality Gate to turn green.
2. In Supabase SQL Editor, run `db/005_automation_hardening.sql` once.
3. Open Commissioner → Week and confirm the green **Automation fallback armed** message.
4. No GitHub workflow file, secret, or hidden file needs changing.
