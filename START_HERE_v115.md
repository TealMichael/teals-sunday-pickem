# Teal’s Sunday Pick’em v1.0.15 — installation and rollback

Prepared October 31, 2026. This is the final background-refresh release package for installation over **v1.0.14**. No deployment or production database change was performed while building it.

The database step is required. Install it **before** the app files. It protects saved scores from expired workers and old app versions. Background execution starts **off** so the new app can first be checked with the same coordinated writer running synchronously.

## Downloads

| File | Use |
| --- | --- |
| `Teals_Sunday_Pickem_v1.0.15_BROWSER_UPLOAD.zip` | Changed/new repository files only; extract and upload its contents at the existing repository root. |
| `Teals_Sunday_Pickem_v1.0.15_FULL_CURRENT_APP.zip` | Complete current source, including the unchanged workflow and earlier migrations; retain as your source backup. |
| `014_background_refresh.sql` | The only new migration to run on the existing v1.0.14 database. |
| `Teals_v115_ROLLBACK_TOOLS.zip` | Maintenance page, v1.0.14 file overlay, and emergency rollback SQL. Keep before installing. |
| `Pickem_v115_Verification_Evidence.zip` | Tests, raw reports, comparisons, and reproduction instructions. Do not upload this ZIP to the app repository. |
| `Pickem_v115_Package_Verification.json` | ZIP hashes and exact file-overlay audit. |

Use the browser-upload ZIP for this update. GitHub does not unpack an uploaded ZIP for you. The full-current ZIP contains many more files than a single browser upload permits.

## Before starting

1. Open the existing Pick’em GitHub repository. Confirm the installed build is v1.0.14, and record its commit from the **Code** page. Use **Code → Download ZIP** to retain the current repository too. Keep the supplied v1.0.14 full-source backup and your existing Supabase backup/recovery option available.
2. Record the current app URL and database project. This application uses the **`pickem` schema** in the existing Supabase project. Do not create a new project or run earlier migrations again. The new script does not alter unrelated application schemas.
3. Choose a quiet time before Sunday’s lock. During the database-first transition the old app can still read saved data, but old protected write attempts are rejected until the new code is running. Avoid commissioner changes during this brief transition.
4. In GitHub, open **Actions → Pickem NFL Refresh → … → Disable workflow**. Open any queued/in-progress runs, cancel them, and wait until they show a terminal status. Disabling alone does not cancel existing runs. Pause any other manually operated copy of the refresh script too. Leave unrelated workflows alone.

## Install in this order

### 1. Apply the database protection

In the correct Supabase project, open **SQL Editor**, create a new query, paste the entire contents of `014_background_refresh.sql`, and run it using the project’s database-owner SQL Editor role. It is one transaction. A reported error means this step is not complete; resolve it before uploading app files. Do not disable its triggers to work around an error.

Then run the contents of `db/operations/VERIFY_v115.sql` from the extracted browser package. Expected results:

- `protocol = 1` and `background_enabled = false` on the first installation.
- `server_can_claim = true`, `anonymous_can_claim = false`, `browser_can_commit = false`.
- `installed_statement_guards = 10`.
- Existing weeks and their saved timestamps remain present.

The migration can be reapplied safely. Reapplying does not reset an already-enabled mode, so use the provided fallback script if intentionally returning to synchronous mode.

### 2. Upload the code together

Extract `Teals_Sunday_Pickem_v1.0.15_BROWSER_UPLOAD.zip`. In GitHub’s **Code** tab at the repository root, choose **Add file → Upload files**. Drag **all files and folders inside** the extracted directory into the upload area. The upload must show `app.py`, `background_refresh.py`, `refresh_protocol.py`, and the other root files at the root, with `db/` and `tests/` retaining their folder paths. Do not upload the outer enclosing folder.

Commit all files together with a message such as `Install v1.0.15 coordinated background refresh`. If your repository uses pull requests, upload to a new branch and merge the complete change into the branch Streamlit deploys. Do not split the Python files into separate deployed commits. The workflow schedule and dependency pins are unchanged; no new secret or service is needed.

In your Streamlit Community Cloud workspace at [share.streamlit.io](https://share.streamlit.io), use the app’s **… → Reboot**, then confirm. Alternatively use **Manage app → … → Reboot app** inside the deployed app. Wait for the reboot to finish and verify **Build 1.0.15**. A page reload alone does not prove that old process memory has been cleared.

### 3. Check synchronous mode first

Keep `background_enabled = false` for these checks:

- Sign in with your existing player PIN; confirm the same player and saved picks appear. Check a remembered session on an already-remembered device.
- Open the linked Commissioner tab and unlock it normally. Confirm Week, Newsletter, Players, Corrections, Clock, and Diagnostics are available.
- Confirm the five positions, backups, visible player pool, season standings, history, and clock settings remain intact. Before lock, starters must stay hidden from other players; after lock, picks must remain locked.
- Use the existing **Refresh NFL data now** commissioner action once for the current week. A concurrent-owner/busy result means retry after that refresh finishes; it is not a reason to remove safeguards. Check Diagnostics for its successful data run. Before lock this uses the existing injury/schedule path; do not force live scoring or finalization just to test the installation.
- Rerun `VERIFY_v115.sql`. Confirm the protocol/permissions/guards and unchanged mode. Preserve the successful app and diagnostics observations with the installation commit.

Finalization, correction set/clear, archive retry, and rollback were tested with synthetic data in disposable PostgreSQL. Do not finalize the real current week early or change real scores merely to repeat those tests. A physical iPhone and hosted-service smoke check are still installation checks, not claims made by the offline report.

### 4. Enable the background mode and restore the scheduled backup

Once the preceding checks pass, run `db/operations/ENABLE_BACKGROUND_v115.sql` in Supabase SQL Editor. It must return `background_enabled = true`.

In GitHub, re-enable **Pickem NFL Refresh**. Choose **Run workflow**, select the newly updated branch, leave `mode = auto`, `week = 0`, and `force = false`, and start one run. Confirm its commit is the new release and the job succeeds. Auto mode can legitimately report no action due when data is already fresh.

On Live Sunday, scores are read from saved data while ESPN work runs separately. The small line above Standings shows an active update or a delay when applicable. It can be absent when nothing is due. The existing 15-second display tick and eight-second shared-bundle cache remain. Confirm roster taps work and that a later completed scoring refresh advances the saved scoring timestamp. A full-scoreboard-only refresh must not advance the fantasy-score timestamp.

## Preferred rollback: retain the protections, turn off background execution

Run `db/operations/FALLBACK_SYNC_v115.sql`. Confirm `background_enabled = false`; keep all v1.0.15 files and the migration installed. This immediately invalidates outstanding candidate ownership. Their late results cannot overwrite saved scores. Subsequent page checks use the coordinated synchronous path; provider waiting can return to the elected page. The independent GitHub job continues on its original schedule.

Reboot the Streamlit app to discard any stuck in-process thread, then repeat the login/picks/commissioner checks. This rollback retains all accounts, picks, scores, and history and was tested. To retry background execution later, use the enable script again.

## Emergency full rollback to v1.0.14

Use this only if retaining v1.0.15 in synchronous mode is insufficient. Do not simply replace app.py with v1.0.14 while the database still expects the new protocol.

1. Run the synchronous fallback script. Disable **Pickem NFL Refresh**, cancel all its queued/running jobs, and confirm they have stopped. Stop any other manual refresh process.
2. Extract `Teals_v115_ROLLBACK_TOOLS.zip`. Upload **only `maintenance/app.py`** to the repository root as `app.py`. Commit, reboot the app, and verify that only the maintenance page is displayed. This explicitly replaces the app process so it cannot keep admitting background work. Do not proceed if you cannot verify the maintenance build and stopped jobs.
3. In Supabase SQL Editor, run the complete `014_restore_v114_AFTER_STOPPING_WRITERS.sql` from the rollback tools. It disables/fences outstanding owners, revokes access to the new RPCs, and removes the new guard/revision triggers. It retains existing account, pick, score, and history data; the additive coordinator tables are left in place. Never drop `pickem` or restore a stale data backup as part of this code rollback.
4. Upload **all contents of `restore_v114/`** from the rollback tools to the repository root in one commit. This restores every original file changed by the release, including `app.py`. The new unused v1.0.15 modules and documentation may remain; v1.0.14 does not import them. Reboot and verify **Build 1.0.14**, player login, saved picks, standings, and Commissioner access.
5. Re-enable the workflow and run `auto` once from the restored branch. Confirm success. The original schedule was never changed.

To reinstall afterward, repeat the database-first installation. Reapplying migration 014 reinstalls its guards and RPC grants; explicitly check the mode is off before starting the new app checks.

## Boundaries and expectations

The app host supplies the faster active refreshes; GitHub supplies the independent scheduled backup. This does not guarantee two-/three-minute updates while the app host is stopped or fresh data during an ESPN outage. A stuck provider thread keeps its one process slot until it returns or the host restarts. Its database authority expires after four minutes for scoring lanes (seven minutes for other coordinated operations), with no renewal; late results are rejected. The scheduled job keeps its existing five-minute job timeout.

## Browser-control references

Official instructions checked October 31, 2026:

- [GitHub: disable and enable workflows](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/disable-and-enable-workflows)
- [GitHub: upload repository files](https://docs.github.com/en/repositories/working-with-files/managing-files/adding-a-file-to-a-repository)
- [Streamlit: reboot an app](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app/reboot-your-app)
