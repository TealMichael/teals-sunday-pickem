# Teal's Sunday Pick'em v1.0.7 Hotfix 7.8 — Faster Live Sunday

## Goal
Reduce live-Sunday lag without turning player phones into NFL-provider clients or materially increasing crash/rate-limit risk.

## Changes
- Shared GitHub live-scoring worker: **15 minutes → 5 minutes** from 11 AM Sunday through the overnight live window.
- Live Sunday Streamlit standings reread: **60 seconds → 30 seconds**.
- Live recovery fallback: effectively **7 minutes stale** (5-minute cadence + 2-minute grace) before an active app session may rescue a delayed shared refresh.
- Pre-lock injury/status polling remains **15 minutes** in the final two hours to avoid unnecessarily tripling the heavier injury path.
- AWTRIX polling stays at **15 seconds**; ticker schedule/content is unchanged.
- No changes to scoring formulas, pools, saved picks, backups, lock behavior, or post-1 PM ticker rotation.

## Why this is safe
Provider work remains centralized in one shared backend job. Player devices only reread Supabase; they do not each call ESPN/NFL providers. Existing leases and due guards still prevent duplicate recovery work.

## Install paths
Repository root:
- `config.py`
- `nfl_sync.py`
- `automation_recovery.py`
- `gate4_ui.py`
- `app.py`

Workflow:
- `.github/workflows/nfl-refresh.yml`

Tests:
- `tests/test_v107_hotfix78_fast_live_refresh.py`

No SQL and no AWTRIX reinstall are required.

## Validation
- `pytest -q`: **257 passed**
- `python -m compileall -q .`: PASS
- `python release_guard.py`: PASS

## GitHub
Commit: `v1.0.7 hotfix — speed up live Sunday refresh cadence`

Tag: `v1.0.7-hotfix7.8`
