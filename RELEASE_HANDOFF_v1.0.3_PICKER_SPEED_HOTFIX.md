# Release Handoff — v1.0.3 Picker Speed Hotfix

## Baseline
`Teals_Sunday_Pickem_v1.0.3_Final_Full.zip` after the Tuesday publication-retry workflow was successfully installed and the Quality Gate was green.

## User-reported issue
The new deliberate picker felt slow because a player-card tap immediately wrote the pick to Supabase before the user pressed Next.

## Locked fix
- Tap = local highlight/checkmark only.
- Next/Return = save the position once, then navigate.
- Questionable starter + emergency backup are committed together.
- Selecting the already-saved choice and pressing Next skips the upsert.
- Back discards the unsaved staged choice.
- Active builder uses a 300-second lineup snapshot to avoid repeated lineup reads while choosing.

## Files changed from v1.0.3 baseline
- `weekly_ui.py` — picker state/save timing
- `app.py` — weekly UI reload schema guard 3 → 4
- contract/regression tests updated for the intentional save-timing change
- new `tests/test_v103_picker_speed_hotfix.py`
- release/handoff/test documentation

## Protected files unchanged
- `store.py`
- `nfl_scoring.py`
- `nfl_sync.py`
- `auth.py`
- `security.py`
- all `db/*.sql` migrations
- `.github/workflows/nfl-refresh.yml` (Tuesday retry schedule preserved)
- `.github/workflows/quality-gate.yml`

## Verification
- pytest: **150/150 PASS**
- full-week rehearsal: **9/9 PASS**
- compileall: **PASS**
- release guard: **PASS**

## Next gate
Freeze after phone verification. Wednesday night remains the Commissioner-only live-stat/scoring dress rehearsal.
