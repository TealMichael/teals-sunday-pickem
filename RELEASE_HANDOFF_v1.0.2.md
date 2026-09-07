# Release Handoff — v1.0.2

## Starting baseline
- File: `Teals_Sunday_Pickem_v1.0.1_Final_Full`
- SHA-256: `6cf1078bc5e6e4e8f679947f6e533b1f859fe5baa491d1b7d2ccb2a38d389011`
- Baseline remains the rollback build.

## Locked scope
This release implements only the two agreed pre-Week-1 polish items:
1. **#3 Weekly Recap**
2. **#5 Sunday Status Card**

No unrelated feature expansion was added.

## What changed
### Sunday Status Card
- One-glance lineup readiness.
- Questionable starters remain visible even when a valid emergency backup is set.
- OUT starters and missing picks are surfaced immediately.
- Compact time until the universal Sunday 1:00 PM ET lock.
- NFL data freshness line, with a stale-data warning inside the final two hours before lock.

### Weekly Recap
Appears after Monday reconciliation marks the week `FINAL`:
- Champion / co-champions
- Most Popular Pick
- Boldest Solo Pick
- Closest Finish
- Same Brain
- Biggest Mover in the season standings
- Week 1 Season Race fallback because no prior standings exist
- Copyable group-chat results summary

## Files intentionally changed
- `app.py` — hot-deploy reload guard versions only
- `config.py` — build version only
- `weekly.py` — read-only lineup-readiness helpers + schema marker
- `weekly_ui.py` — Sunday Status Card + hot-deploy guard
- `gate4.py` — recap/share calculations + schema marker
- `gate4_ui.py` — FINAL recap/share presentation + hot-deploy guard
- `ui.py` — status/recap styling
- release/readme/test documentation
- version-contract tests + new v1.0.2 tests

## Explicitly unchanged
- Scoring rules
- Kicker scoring
- Universal Sunday 1:00 PM ET lock
- Emergency-backup activation contract
- Weekly/season points and tie handling
- PIN/auth/remembered-device behavior
- Commissioner business rules
- NFL provider/scoring pipeline
- Supabase schema/settings
- GitHub Actions schedule/workflows

## Verification
- `pytest -q`: **138/138 PASS**
- Full Week Rehearsal: **9/9 PASS**
- `python -m compileall -q .`: **PASS**
- `python release_guard.py`: **PASS**

## Deferred until after Week 1
- Invite/share flow with Copy Link / QR
- Push notifications
- Deeper Season personality/stats
- Expanded Commissioner recovery/backup tools

## Install
No SQL, Supabase, secret, or workflow changes are required. Upload the v1.0.2 files to the existing repository, commit to `main`, verify the GitHub Quality Gate, then run Commissioner Launch Check + Full Week Rehearsal.

Suggested commit: `v1.0.2 — Sunday Confidence + Weekly Recap`
