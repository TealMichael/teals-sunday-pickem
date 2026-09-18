# Hotfix 7.15.2 — Quality Gate test alignment

The mobile navigation adjustment in 7.15.2 intentionally changed the iPhone
bottom offset from `5.5rem` to `4.1rem` and incremented the UI schema to 4.
Three existing regression-test modules retained exact assertions for the old
position, build marker, or UI schema, so they failed even when the current
CSS and warm-deploy guards were correct.

Only `tests/test_v101_mobile_launch_polish.py`,
`tests/test_v107_hotfix715_ui_polish.py`, and
`tests/test_v107_hotfix7151_profile_nav_clearance.py` are adjusted to assert
the current offset and hotfix7.15.2 build/schema. The newer 7.15.2 docking test
remains in the repository unchanged.

A reconstructed cumulative app passed 322 tests, compilation, and release_guard
following the test alignment. The latest live GitHub failure details were not
available in the screenshot, so this addresses the locally reproduced failing
assertions; inspect GitHub's failing test log if the rerun stays red.

Commit: `v1.0.7 hotfix — align mobile nav tests with 7.15.2`
Tag: `v1.0.7-hotfix7.15.2-ci-repair`

This is TESTS ONLY. No runtime source, database, or workflow changes.
