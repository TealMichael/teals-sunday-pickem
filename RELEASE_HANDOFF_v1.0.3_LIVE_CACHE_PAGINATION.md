# Release Handoff — v1.0.3 Live Cache Pagination Diagnostic Hotfix

Baseline: v1.0.3 Live Identity Diagnostic.

Scope: Commissioner Diagnostics only. Fixes the 1000-row cached-player read used by the Wednesday identity diagnostic by loading QB/RB/WR/TE/K separately and deduplicating.

Runtime change: `live_dress_rehearsal.py` only.
Test change: `tests/test_commissioner_live_dress_rehearsal.py`.

Protected production behavior unchanged: public UI, signup, lineup picker, player pool, scoring formulas, `nfl_sync.py`, `store.py`, auth, SQL migrations, GitHub workflows.

Verification: 162/162 pytest PASS; 9/9 Full Week Rehearsal PASS; compile PASS; release_guard PASS.
