Teal's Sunday Pick'em v1.0.7-hotfix6 — CI/source alignment repack

Why this repack exists:
GitHub's Hotfix 5 regression test expects the current production AWTRIX reference
script to contain the 15-second polling fallback (`self.ticks = 15`), but the
repository had an older copy of awtrix/PickemSunday.ax.

This repack contains the same Hotfix 6 production app code plus:
- awtrix/PickemSunday.ax from the audited full source-of-truth build
- tests/test_v107_hotfix5_clock_score_cadence.py explicitly paired with it

IMPORTANT:
Uploading this AWTRIX source file to GitHub does NOT change the physical clock.
No AWTRIX reinstall is required.
No Supabase SQL is required.
No hidden file changes are included.

After upload, verify these two repository files exist:
- awtrix/PickemSunday.ax
- tests/test_v107_hotfix6_sunday_stability.py

Then rerun / wait for Pickem Quality Gate.
