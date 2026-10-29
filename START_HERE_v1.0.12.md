# Teal’s Sunday Pick’em v1.0.12

This release fetches up to three ESPN game summaries at once so a live scoring refresh spends less time waiting. It preserves the existing interface, scoring, game coverage, refresh schedules, commissioner protections and recovery behavior.

**Version:** 1.0.12  
**Build:** 1.0.12-performance3  
**Git tag:** v1.0.12  
**Starting source:** v1.0.11 / 1.0.11-performance2

## Install through GitHub in your browser

1. Open the **Teal’s Sunday Pick’em football repository**. Confirm its `config.py` currently says `APP_VERSION = "1.0.11"` and `APP_BUILD_VERSION = "1.0.11-performance2"`. This small upload bundle is based on that exact version. Reconcile an older/newer repository before applying this partial update. Installation of v1.0.11 was not confirmed during development.
2. Download and unzip `Teals_Sunday_Pickem_v1.0.12_GITHUB_BROWSER_UPLOAD.zip`.
3. At the repository root, select **Add file → Upload files**. Drag the **contents of `UPLOAD_TO_GITHUB`** into the upload area. Preserve the `tests` and `performance_evidence` folders. Do not drag the outer ZIP folder or the `ROLLBACK_ONLY` folder. The destination should have `app.py` directly at the repository root.
4. Use this exact commit message:

   `perf: release v1.0.12 with bounded concurrent ESPN summary retrieval`

5. Commit through your usual GitHub flow. If you use a pull request, wait for **Pickem Quality Gate** to pass and then merge it. If you normally commit directly to the deployment branch, monitor the same quality gate after the upload.
6. After the normal Streamlit deployment, reload the app and verify **Build 1.0.12** in Profile. Check remembered login, your saved starters/backups, player/Commissioner access and normal navigation. During normal live use, verify the usual standings, ticker and score-age display. No database setup, secret change, dependency change or AWTRIX installation is required.

The complete app ZIP is a full source copy for reference and recovery. The smaller browser bundle is the upload intended for an existing v1.0.11 repository. No remote repository, deployment or production data was changed by this release preparation.

## Roll back through GitHub

If you merged a pull request for this release, open that merged pull request, choose **Revert**, and merge the resulting revert pull request after its checks pass. GitHub’s [revert instructions](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/reverting-a-pull-request) describe this flow.

For a direct browser upload, the ZIP also includes **`ROLLBACK_ONLY`**:

1. In the football repository, delete `tests/test_v112_espn_concurrency.py` using the file’s delete action and commit the deletion. This removes tests for the newer provider API; it does not change the running app.
2. Upload the **contents of `ROLLBACK_ONLY`** at the repository root, keeping its `tests` folder. These six files are exact originals from v1.0.11. Commit with `revert: restore v1.0.11 ESPN retrieval`.
3. Wait for the quality gate and normal deployment. Profile should show **Build 1.0.11**. The retained release documents, evidence and synthetic fixture helper do not affect the v1.0.11 app.

This returns application behavior to v1.0.11 without restoring the database or touching saved picks, users, scores or clock settings. If you have made later application changes, review those before reverting this release.

## Validation and limits

- **446 tests passed on Python 3.12 and 3.13**, including 23 new cases.
- In an identical synthetic ten-game workload, the active scoring refresh took about **0.62 seconds before and 0.26 seconds after**, with the same requests and database operations.
- Scoring, saved-pick, standings, archive, achievement, newsletter and clock-output comparisons matched.
- This is measured synthetic refresh performance. It is not a measured iPhone page-load improvement, and warm pages without ESPN work do not directly benefit.

See `V1_0_12_TEST_REPORT.md` and `V1_0_12_PERFORMANCE_RESULTS.json` for the full report and reproducible evidence.
