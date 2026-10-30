# Teal’s Sunday Pick’em v1.0.14

This update makes Live Sunday standings cheaper to load and opens/closes a standings roster in one page run. The same screens, scoring, controls, privacy rules and refresh schedules remain. No database migration or settings change is required.

Version **1.0.14** · build **1.0.14-performance5** · proposed tag **v1.0.14**.

## Install through GitHub in your browser

1. Open the **Teal’s Sunday Pick’em football repository**. In `config.py`, confirm `APP_VERSION = "1.0.13"` and `APP_BUILD_VERSION = "1.0.13-performance4"`. If you have not installed v1.0.13, install that update first. This small update is based on the exact v1.0.13 full source; reconcile any later edits before applying it.
2. Download and unzip `Teals_Sunday_Pickem_v1.0.14_GITHUB_BROWSER_UPLOAD.zip`. Open `UPLOAD_TO_GITHUB`.
3. At the repository root, choose **Add file → Upload files**. Drag the **contents of `UPLOAD_TO_GITHUB`**, including its folders. Keep `tests` and `performance_evidence` intact. `app.py` belongs directly at the repository root. Leave `ROLLBACK_ONLY` out of this upload.
4. Use this commit message:

   `perf: streamline live standings reads and roster taps in v1.0.14`

5. Follow your normal commit flow. For a pull request, wait for **Pickem Quality Gate** to pass before merging. For a direct commit, monitor the same check after uploading. It runs the regression tests, compilation and release guard on Python 3.13.
6. After the normal Streamlit deployment, reload the app and confirm **Build 1.0.14** in Profile.

Use the full app ZIP as the complete source backup and for future work. The browser-upload ZIP contains this upgrade and its rollback files. No remote repository, deployment or production data was changed during preparation.

## Quick checks before Sunday

- Remembered login and the usual player/Commissioner access still work.
- Your saved five and emergency backups remain correct. In an allowed pre-lock lineup, check a card tap, Next, Back, Review and Save.
- In a live/results view, tap your standings row to open it, tap again to close it, then switch between two other players. Confirm names, points and scoring details remain correct.
- Your inactive backup stays private; an activated backup displays as usual. Reactions and Season/History/Profile navigation still work.
- During live play, check the normal score-freshness display and AWTRIX ticker. This update keeps the existing refresh schedules.

A due ESPN refresh can still delay the one session performing it. This update reduces database work and roster reruns; it does not guarantee that every Sunday pause is gone.

## Roll back through GitHub

If installed through a pull request, use **Revert** on the merged request and merge the revert request after its checks pass.

For a direct browser upload:

1. Delete these four newly added test/fixture files from the repository and commit the deletion:
   - `tests/test_v114_public_bundle.py`
   - `tests/test_v114_roster_callbacks.py`
   - `tests/public_bundle_fixture.py`
   - `tests/public_query_fixture.py`
2. Upload the **contents of `ROLLBACK_ONLY`** at the repository root, preserving its `tests` folder. It contains the eight exact original files changed by this release. Commit with `revert: restore v1.0.13 live standings`.
3. Wait for the quality gate and normal deployment. Profile should show **Build 1.0.13**. Extra v1.0.14 documents/evidence can remain; they do not run in the app or regression suite.

This procedure restores all 342 original v1.0.13 files byte for byte and passed all 479 original tests on Python 3.13.16. It does not alter the database. Review subsequent changes before rolling back.

## Validation

**555 tests passed on Python 3.12.14 and 3.13.16.** There are 76 new regression cases. Another 76 before/after complete-app scenario pairs matched for displayed element trees, button labels/order, saved choices, modes, errors and reactions. Twelve consumer fingerprints matched in 36 scenarios, including 30 shuffled equal-name tie cases. The browser payload overlays onto the exact baseline to reproduce the full release byte for byte.

These are automated, offline checks with synthetic database/provider waits. They are not production or physical iPhone measurements. See `V1_0_14_TEST_REPORT.md` and `performance_evidence/v1_0_14/README.md` for evidence and reproduction.
