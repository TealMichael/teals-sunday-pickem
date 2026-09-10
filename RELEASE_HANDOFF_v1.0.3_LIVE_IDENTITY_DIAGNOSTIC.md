# Release Handoff — v1.0.3 Live Identity Diagnostic

Baseline: `Teals_Sunday_Pickem_v1.0.3_Final_Full_LIVE_TEST_POSITION_HOTFIX.zip`

Purpose: use the live Wednesday game to explain exact ESPN ↔ cached Sleeper identity misses before changing production scoring. This patch remains Commissioner-only and read-only.

Changed runtime files:
- `live_dress_rehearsal.py`
- `gate5_ui.py`

Changed/additional test/docs:
- `tests/test_commissioner_live_dress_rehearsal.py`
- `V1_0_3_LIVE_TEST_IDENTITY_DIAGNOSTIC.md`
- this handoff

Do not change production identity matching until the live diagnostic identifies whether misses are stale-team assignments, absent cached players, or name variations.
