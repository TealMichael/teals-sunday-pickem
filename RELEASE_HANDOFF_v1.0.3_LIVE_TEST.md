# Release Handoff — v1.0.3 Commissioner Live Test

## Baseline
`Teals_Sunday_Pickem_v1.0.3_Final_Full_PICKER_RERUN_HOTFIX.zip`

This is the exact friend-facing build that was verified smooth on the phone and sent to friends on September 8, 2026.

## Scope locked
Commissioner-only Wednesday live-game diagnostic. No public feature or production scoring behavior changes.

## Files changed from baseline
- `gate5_ui.py` — adds the Commissioner → Diagnostics live rehearsal UI and passes current real-week context into Diagnostics.
- `live_dress_rehearsal.py` — new read-only provider/parser/scoring diagnostic.
- `tests/test_commissioner_live_dress_rehearsal.py` — verifies live parser/scoring/matching and read-only contract.
- `V1_0_3_COMMISSIONER_LIVE_TEST.md`
- this handoff

## Explicitly unchanged
- `app.py`
- `ui.py`
- `weekly_ui.py`
- `store.py`
- `nfl_scoring.py`
- `nfl_sources.py`
- `nfl_sync.py`
- `auth.py`
- all SQL migrations
- `.github/workflows/nfl-refresh.yml`
- `.github/workflows/quality-gate.yml`

Therefore the public signup/picker/status experience and the production Sunday write pipeline remain byte-for-byte the same as the current friend-facing baseline.

## Wednesday procedure
1. Commissioner → Diagnostics.
2. Open **Wednesday Live Game Dress Rehearsal**.
3. Click **Load / refresh current-week games**.
4. Select the Wednesday night game.
5. Before kickoff you may run once to confirm CONNECTION PASS.
6. After kickoff run **Run Live Game Test Now**.
7. Repeat after several plays and again ~10–15 minutes later.
8. Look for LIVE status, active scoring rows, strong Sleeper match rate, changed stat lines between snapshots, and scoring math that agrees with the broadcast/box score.

## Verification
- 156/156 pytest PASS
- 9/9 Full Week Rehearsal PASS
- Python compile PASS
- release_guard PASS

## Next
If Wednesday is green, freeze the production pipeline. Thursday scoring-detail work, if any, should be presentation-only.
