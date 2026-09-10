# Release Handoff — v1.0.5 Tap-to-Edit Lineup Review

## Baseline
Built directly from the installed v1.0.4 Public UX Polish source-of-truth baseline after the successful Wednesday live-scoring rehearsal and identity-cache diagnostic fixes.

## Runtime scope
- `weekly_ui.py` — replaces the static Review My Five summary + secondary Change buttons with native full-card edit targets; preserves emergency-backup context; allows OUT cards to open for replacement.
- `config.py` — APP_VERSION 1.0.5.
- `app.py` — weekly UI schema reload guard bumped to 7 for safe Streamlit hot deployment.

## Test scope
Version/schema contract tests were advanced to v1.0.5 and a dedicated tap-to-edit regression test was added.

## Protected behavior
Byte comparison against v1.0.4 confirmed no changes to `nfl_scoring.py`, `nfl_sync.py`, `store.py`, `auth.py`, `security.py`, `live_dress_rehearsal.py`, `gate5.py`, `gate5_ui.py`, `nfl_rankings.py`, `nfl_sources.py`, `weekly.py`, or either GitHub Actions workflow.

## Verification
- pytest: 172/172 PASS
- Full Week Rehearsal: 9/9 PASS
- compileall: PASS
- release_guard: PASS

## Deployment
No hidden files, SQL, secrets, Supabase settings, or workflow files need updating.
