Teal's Sunday Pick'em v1.0.7-hotfix6 — Audited Repository Sync

The GitHub Quality Gate exposed repository drift across several historical source files:
- stale awtrix/PickemSunday.ax
- stale tests/test_v107_sunday_clock.py
- missing db/007_awtrix_clock_rpc_hotfix.sql

Instead of correcting one file at a time, this package synchronizes all NON-HIDDEN runtime,
database-script, AWTRIX-source, worker, and test files to the exact audited Hotfix 6 source tree.

IMPORTANT:
- Upload everything at repository root, preserving folders.
- db/*.sql files are source/history files only. Uploading them does NOT execute SQL.
- Do NOT rerun old Supabase migrations.
- No physical AWTRIX reinstall is required.
- No .github or .streamlit files are included or changed.

The exact full audited Hotfix 6 tree from which this package was built passes 217/217 tests.
