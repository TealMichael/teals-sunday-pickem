# Teal’s Sunday Pick’em v1.0.10 — Performance Round 1

**Release version/tag:** `v1.0.10`  
**Internal build:** `1.0.10-performance1`  
**Prepared:** October 27, 2026  
**Base:** the exact uploaded `Teals_Sunday_Pickem_v1.0.9_FULL_CURRENT_APP.zip`

This release implements the four approved first-round performance improvements. It retains the unified player/commissioner login and every existing control, scoring rule, lineup protection, page, social feature and refresh schedule. No direct deployment was performed.

## Changelog

1. **Reuse the database connection client.** The `pickem` schema is selected when creating the Supabase client. Table queries reuse its initialized HTTP transport rather than constructing another transport per operation. Credentials, timeouts, query payloads and schema routing are preserved.
2. **Reuse completed player-card statistics.** Successful weekly frozen snapshots are cached on the store with independent copies for callers. Missing, failed, empty and retry-marker values are not frozen. Confirmed writes to the same snapshot key invalidate its cached copy. Authentication and mutable settings remain uncached.
3. **Read the initial pregame lineup once.** The status fragment returns its fresh lineup data for the home page to reuse. Every independent status refresh still performs recovery checks and reads the current lineup. The 60-second status timer and 15-second lock guard are unchanged.
4. **Read the Corrections pool once per ordinary render.** Preview and score controls share the already-loaded pool. Submitted actions retain their original validations. A failed pool mutation still rereads the pool before rendering score controls.

Build/reload identifiers were updated so an existing Streamlit worker picks up the changed modules and creates a fresh store. Twenty-six regression cases were added; three existing test adapters were updated while retaining their schema-routing and display-order assertions.

## Measured before and after

These are offline measurements using the same synthetic data and original application functions. Database counts are logical requests, not page-load milliseconds.

| Scenario | v1.0.9 | v1.0.10 |
| --- | ---: | ---: |
| New HTTP clients for 100 table-query preparations, after initialization | 100 | **0** |
| Warm picker render | 1 read | **0 reads** |
| Tap a player card | 1 read, no write | **0 reads, no write** |
| Next with a changed pick | 3 reads + 1 write | **1 read + 1 write** |
| Cold pregame home | 6 reads | **5 reads** |
| Cold Corrections page | 9 reads | **7 reads** |
| Warm Corrections page | 8 reads | **6 reads** |

Normal live polling retains its 15-second display cadence and measured 7–9 reads per tick. The shared transport now applies to those reads too. Moving synchronous NFL refresh work out of page rendering was deliberately left for a separately approved release; this update does not eliminate every possible provider-related pause.

Validation passed: **412 tests on Python 3.12 and Python 3.13**, compilation of all 114 Python files, and the release guard. Before/after comparison matched page content and controls across 19 scenarios, allowing only the version label to change. Saved selections, weekly and season standings, story/achievement output, newsletter text, and clock payloads matched in the synthetic comparison. See `V1_0_10_TEST_REPORT.md` for scope and limits.

## Which ZIP to use

- **GitHub Browser Upload ZIP:** use this to update the existing football repository. It contains only the 15 changed/new application, test and release-document files under `UPLOAD_TO_GITHUB`.
- **Full Current App ZIP:** keep this complete 275-file project for backup or a future handoff. It contains the full application, including existing SQL, workflows and historical documentation.

There are **no new dependencies, SQL migrations, secrets, database cleanup steps or clock-script installation steps**.

## Install using GitHub in your browser

1. Download and unzip `Teals_Sunday_Pickem_v1.0.10_GITHUB_BROWSER_UPLOAD.zip` on your Mac.
2. Open your existing **Sunday Pick’em football repository** on GitHub. Confirm you are at its root, where `app.py`, `config.py` and `store.py` are visible.
3. Choose **Add file → Upload files**.
4. Open the extracted `UPLOAD_TO_GITHUB` folder in Finder. Drag **its contents**, including the `tests` folder, into GitHub. Do not drag the outer `UPLOAD_TO_GITHUB` folder or the ZIP itself. Preserve the `tests/...` paths.
5. Check that `app.py`, `store.py`, `weekly_ui.py` and the other files are replacing/adding files at the expected root paths. There should be 15 files in this update, with no extra enclosing folder.
6. Paste the commit message below. Commit to the branch your Streamlit app already uses, following your normal repository workflow. If that branch requires a pull request, use a new branch and merge after the quality check passes.
7. Wait for **Pickem Quality Gate** to pass and for the normal Streamlit update to finish. Reload the app and confirm **Build 1.0.10** on Profile.

GitHub’s upload controls are documented in its [official file-upload guide](https://docs.github.com/en/repositories/working-with-files/managing-files/adding-a-file-to-a-repository). No terminal commands are needed for this installation.

## Quick checks after installation

- Your remembered player login still works, and your linked Commissioner tab remains available.
- Sunday, Season, History and Profile open normally.
- Saved five-player selections and backups are intact. Card taps highlight; Next saves, as before.
- Commissioner Home still has Week, Newsletter, Players, Corrections, Clock and Diagnostics.
- Existing newsletter and clock settings are present. Avoid live reset, regeneration, finalization or test-broadcast actions just to validate the update.
- During the next live slate, observe scoring freshness and responsiveness. A real iPhone/live-provider timing comparison has not been performed here.

## Exact commit message

```text
perf: release v1.0.10 with connection reuse and fewer duplicate reads
```

Use **`v1.0.10`** if you create a GitHub release/tag. No remote commit or tag was created by this handoff.

## Rollback

Revert this single upload commit through your normal GitHub workflow if needed, returning to the previous application files. There is no database migration to undo and no game data to restore. Do not reset or regenerate the live week as part of rollback.

The broader cache/concurrency, refresh-worker, query-joining and UI-rerun changes from the audit remain outside this release.
