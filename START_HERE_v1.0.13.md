# Teal’s Sunday Pick’em v1.0.13

This release removes the extra full page run from ordinary lineup navigation and successful saves. The same buttons, cards, saved choices and freshness checks remain. No database migration or settings change is required.

**Version:** 1.0.13  
**Build:** 1.0.13-performance4  
**Proposed Git tag:** v1.0.13  
**Starting source:** v1.0.12 / 1.0.12-performance3

## Install through GitHub in your browser

1. Open the **Teal’s Sunday Pick’em football repository**. In `config.py`, confirm `APP_VERSION = "1.0.12"` and `APP_BUILD_VERSION = "1.0.12-performance3"`. This update was built from the exact v1.0.12 full-source ZIP. If your repository differs, reconcile it before applying this partial update; the running version was not confirmed during preparation.
2. Download and unzip `Teals_Sunday_Pickem_v1.0.13_GITHUB_BROWSER_UPLOAD.zip`. Open `UPLOAD_TO_GITHUB`.
3. At the repository root, use **Add file → Upload files**. Drag the **contents of `UPLOAD_TO_GITHUB`**, including its folders, into the upload area. Preserve `tests` and `performance_evidence`. `app.py` should be directly at the repository root. Leave `ROLLBACK_ONLY` out of the upload.
4. Use this commit message:

   `perf: avoid duplicate lineup navigation and save reruns in v1.0.13`

5. Follow your normal GitHub commit flow. For a pull request, wait for **Pickem Quality Gate** to pass before merging. For a direct commit, monitor that same check after uploading. The existing gate runs the tests, compilation and release guard on Python 3.13.
6. After your normal Streamlit deployment, reload the app and check **Build 1.0.13** in Profile. In a permitted pre-lock lineup, check Build/Continue, a card tap, Next, Back, Review, Save and Edit. Verify your saved starters/backups, remembered login and normal player/Commissioner access. During live use, check the usual standings, ticker and freshness display.

The full app ZIP is the complete source for reference and recovery. Use the browser-upload ZIP for this upgrade. No remote commit, deployment or production data change was performed during preparation.

GitHub’s [browser upload instructions](https://docs.github.com/en/repositories/working-with-files/managing-files/adding-a-file-to-a-repository) describe the upload controls.

## Roll back through GitHub

If you installed through a pull request, open the merged request, choose **Revert**, and merge the resulting revert request after its checks pass. See GitHub’s [revert instructions](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/reverting-a-pull-request).

For a direct browser upload:

1. Delete `tests/test_v113_lineup_actions.py` and `tests/lineup_ui_fixture.py` from the repository and commit the deletion. These are the two new test files; removing them does not change the running app.
2. Upload the **contents of `ROLLBACK_ONLY`** at the repository root, preserving its `tests` folder. It contains the seven exact original files changed by this release. Commit with `revert: restore v1.0.12 lineup navigation`.
3. Wait for the quality gate and normal deployment. Profile should show **Build 1.0.12**. The extra release documents and evidence can remain; they do not run in the app or the regression suite.

This procedure restores all 302 original v1.0.12 files byte for byte and was checked with all 446 original tests on Python 3.13.16. It does not restore or alter the database. Review any later application changes before rolling back.

## Validation

- **479 tests passed on Python 3.12.14 and 3.13.16**, including 33 new cases.
- **185 before/after scenario pairs** matched for the final rendered UI tree, button labels/order, saved picks, modes and errors. Runtime IDs and the intended Build version label were normalized.
- Targeted ordinary actions changed from **two full page runs to one**. Required database reads and writes stayed equal; linked-owner sessions avoid the permission lookup associated with the removed run and still check permissions on every remaining run.
- The small upload overlaid onto the exact v1.0.12 source matches the full v1.0.13 package byte for byte. Compilation and release guard passed.

These are automated and synthetic application measurements. Physical iPhone/Safari performance and production latency were not measured. See `V1_0_13_TEST_REPORT.md` for details and `performance_evidence/v1_0_13/README.md` for reproduction.
