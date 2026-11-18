# Teal's Sunday Pick'em v1.0.19 — 🦃 Turkey Bowl installation

**Base:** uploaded full source `teals-sunday-pickem-main(4).zip`, build v1.0.18.  
**Purpose:** separate 2026 Thanksgiving game, full extra season points, next-season 🦃🏆.  
**Order is important:** existing Supabase **SQL first**, then one complete GitHub browser upload, then hosted smoke checks. Do not create a new Supabase project.

## First: back up your live v1.0.18

1. In the existing `teals-sunday-pickem` GitHub repository, record the **current commit** on `main`. Select **Code → Download ZIP** as a recovery copy.
2. Keep the existing database intact. If you use Supabase backups, verify one is available. Do not delete your `pickem` schema or modify Yahtzee's `public` schema.
3. Install outside a game or pool-opening window where possible. The new holiday scheduler does not run until Tuesday, November 24.

## Step 1: Supabase SQL (required)

1. Open your **existing shared Supabase project** that already hosts the Pick'em app (the same one used for v1.0.18).
2. Open **SQL Editor → New query**. Paste and run the entire standalone `Pickem_v1.0.19_Turkey_Bowl_Supabase_SQL.sql` file. It is identical to `db/018_turkey_bowl.sql` in the code package.
3. **Do not upload the new Python files if the migration reports an error.** Keep the currently working application online and inspect the error first.
4. Run the read-only `db/operations/VERIFY_v119_TURKEY_BOWL.sql` query. Expected: exactly one `turkey_bowl` event for **2026 / NFL Week 12 / November 26**, lock at **13:00 Eastern**; all **six** special-event tables have row-level security `true`. Before publication, the pool and games may have zero rows.
5. The migration adds six special-event tables and event-specific lineup guards; it does not replace ordinary Sunday lineup or scoring tables. It updates the *existing* account-removal function to preserve historical Turkey Bowl records.

## Step 2: GitHub browser install (your normal method)

1. Extract `Teals_Sunday_Pickem_v1.0.19_Turkey_Bowl_BROWSER_UPLOAD.zip` on your Mac.
2. Open the **existing** `teals-sunday-pickem` GitHub repository, branch **main**, then **Add file → Upload files**.
3. Open the extracted `teals-sunday-pickem-main` folder and drag **all files and folders inside it** onto GitHub's upload area. **Do not upload the enclosing folder** and **do not upload the ZIP itself**. New `.github/workflows/turkey-bowl.yml` must be uploaded at its exact path. If hidden folders don't appear in Finder, use **Command + Shift + .**
4. Check the GitHub upload list includes `app.py`, `config.py`, `turkey_bowl.py`, `turkey_bowl_ui.py`, `scripts/turkey_refresh.py`, `db/018_turkey_bowl.sql`, `db/operations/VERIFY_v119_TURKEY_BOWL.sql`, and `.github/workflows/turkey-bowl.yml` in the correct locations. Do not omit existing changed files such as `gate4_ui.py` and `weekly_ui.py`.
5. Commit all changed/new files to **main in one commit** with this message:
   **`v1.0.19 — Add Thanksgiving Turkey Bowl and 2027 trophy`**
6. Streamlit Community Cloud should redeploy; reboot the application from **Manage app** if it continues to show the previous build. Confirm the profile footer shows **Build 1.0.19**.
7. Check GitHub **Actions → Pickem Quality Gate** is green. A separate **Pickem Turkey Bowl** scheduled workflow should now exist; it uses existing `SUPABASE_URL` and `SUPABASE_SECRET_KEY` GitHub secrets. No extra secret, AWTRIX update, or second Streamlit app is needed.

## Step 3: Smoke-check without touching live Sunday picks

1. Sign in as your usual player. Confirm existing Week 11/12 Sunday picks, account session, mobile navigation, season standings, History, and Profile are unchanged.
2. On the Sunday screen, look for the **🦃 Teal's Turkey Bowl** card. Open and back out. Before Nov 24, it should explain that the holiday pool is not yet available.
3. Open your **existing linked Commissioner** account, then **Commissioner → Week → 🦃 Turkey Bowl Controls**. Verify it says **not published** before Tuesday noon, November 24. Do not try to force publication early or edit your normal Sunday pool.
4. In GitHub → Actions → **Pickem Turkey Bowl**, you may use **Run workflow** now to verify the job launches and logs `outside event window`; it must not add a game or publish a pool before opening. If the workflow fails, investigate before the 24th.
5. Confirm your existing **Pickem NFL Refresh** workflow is still enabled and regular Sunday behavior continues unchanged.

## Step 4: Tuesday Nov 24 — opening check

1. At or after **12 PM ET**, open Turkey Bowl and verify exactly **five visible choices in each of QB, RB, WR, TE, K**. All names must belong to the **six Thursday teams**: CHI, DET, PHI, DAL, KC, BUF.
2. Choose a Thanksgiving starter and emergency backup, save all five, and press **Confirm my Turkey Bowl lineup**. Verify those holiday selections do **not** change any Sunday selections. Check on another device/session if available.
3. In Commissioner, verify submitted/confirmed counts. The independent GitHub worker attempts to publish at ~12:07 ET and retries. If the pool has not published, inspect the Turkey Bowl workflow error; **do not circumvent the game-verification or five-healthy-choices safeguards**.

## Step 5: Thursday Nov 26 — game and Friday awards checks

1. Recheck your picks and backups **before Thursday 1 PM ET**. Every holiday position locks together at that time, including players in the later games.
2. After the lock, Turkey Bowl standings reveal all saved lineups. Holiday scores should update using the separate GitHub job approximately every five minutes (external services/scheduled jobs may lag). Check Friday after **9 AM ET** for finalized rankings. If not finalized, the worker continues scheduled recovery; check job logs and Commissioner controls.
3. The extra season points appear only after the holiday's three games and player scores have all finalized. Verify Week 12 **Sunday** still takes ordinary selections independently and remains active.
4. The **2026 Turkey Bowl champion's 🦃🏆 badge** is stored immediately in event history; it appears next to the winning nickname in **2027** season views, as requested.

## Rollback / recovery

- **Preferred:** If the Turkey Bowl page is defective but Sunday still works, leave the current database migration in place and investigate app/UI or scheduled workflow problems. The special-event workflow is independently disableable at GitHub Actions.
- **Code rollback:** Re-upload the recorded pre-install **v1.0.18 GitHub ZIP** and reboot Streamlit. The additive holiday tables may remain unused. **Do not reverse the updated `commissioner_remove_account` protection without reviewing the stored Turkey Bowl historical records.** Do not downgrade database refresh coordinator protections or re-run old migrations.
- **Never delete Sunday picks, lineup tables, or season results to troubleshoot Turkey Bowl.** The migration does not require any Sunday data cleanup.
- If GitHub quality checks or live Supabase SQL fail, do not assume a partial installation is correct. Preserve the existing app until fixed.

## Verification limits

The feature was developed and offline-tested against your uploaded v1.0.18 archive. Python syntax checks, the release guard, and selected rules/contract tests passed. This environment could not install or run the complete Streamlit/Supabase dependency suite, execute the SQL against your live database, or run a physical iPhone/cloud integration smoke test. **GitHub Quality Gate and the live checks above are mandatory production validation, not already-completed steps.**
