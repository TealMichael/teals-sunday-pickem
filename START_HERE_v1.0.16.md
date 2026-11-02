# Teal's Sunday Pick'em v1.0.16 — Commissioner-approved accounts

**Install in this order. Do not upload the Python code before the SQL migration.**

## Step 1 — Existing shared Supabase project (required)
1. Open the Supabase dashboard. Select the project whose URL starts with `https://cvczehvorpbwooueebxp.supabase.co`. This shared project contains both Yahtzee (`public`) and Football (`pickem`).
2. Open **SQL Editor → New query**.
3. Paste the entire contents of **`db/015_commissioner_approval_accounts.sql`** (a standalone SQL copy is also provided with the download).
4. Click **Run**. Confirm it says **Success**. This migration only changes the `pickem` schema, never Yahtzee tables or existing lineups/results.
5. Optional read-only verification query:
   ```sql
   select nickname, account_status, created_at
   from pickem.players order by created_at desc limit 15;
   ```
   Existing accounts should show `approved`. The two unwanted accounts remain until you remove them in Step 4. Newly submitted requests after this change will start as `pending`.

**Do not proceed if the migration fails.** Leave the live v1.0.15 app as-is, and send the SQL error for review. Avoid creating accounts during the short interval between SQL and app deployment.

## Step 2 — GitHub browser upload
1. Open your existing `teals-sunday-pickem` GitHub repository on branch **main**.
2. Upload/replace the files **inside** the downloaded ZIP's `teals-sunday-pickem-main` folder into the repository at the same relative paths. Do not nest another `teals-sunday-pickem-main` folder inside the repository. Preserve `.streamlit` and `.github` directories.
3. Commit the changes to `main` with this exact commit message:
   `v1.0.16 — Commissioner approvals and safe account removal`
4. Streamlit Community Cloud should redeploy automatically. You **do not** need new Streamlit secrets, GitHub secrets or an AWTRIX update.
5. GitHub → **Actions** → **Pickem Quality Gate** should pass.

## Step 3 — Check the app
1. Confirm the build version shows `1.0.16`.
2. Sign in with the existing Commissioner-linked player account (or emergency Commissioner access), open **Commissioner → Players**.
3. Confirm **New player requests** and **Remove an account** appear.
4. Existing family players must remain signed in normally and keep their previous picks, PINs and game history.
5. Optional private smoke test: submit an account request using an unused temporary nickname. It must not log in. Check that it appears in Pending, approve, sign in with the PIN, and then safely remove the temporary account.

## Step 4 — Remove the unknown accounts
1. Commissioner → Players → **Remove an account**.
2. Select **Not**, click **Review account removal**, then **Confirm removal**.
3. Repeat for **Not unk**.
4. Accounts with *no* history are permanently deleted. If a player has lineups, picks, or archived results, the account is disabled instead, and all remembered sessions are revoked, preserving game history. The Commissioner owner is protected from removal.
5. Confirm the mystery names no longer appear in the ordinary player list.

## Important boundaries and rollback
- Approval is required for **new accounts**, but the site URL itself remains publicly reachable and anyone can submit a limited number of requests. A shared invitation code is **not** required (Option A).
- The signup burst guard allows at most eight pending requests in an hour and twelve pending requests overall. This is intentional for a small private game.
- Account removal cannot be undone by an end-user. Confirm the selected nickname before removing.
- **Do not roll back only the app code to v1.0.15** after applying the migration: older code did not enforce approval, so it could let pending players play. If a rollback is needed, use a reviewed coordinated security-safe rollback procedure instead.
- The migration does not touch Yahtzee's `public` schema or alter Sunday scoring, NFL refresh, commissioner permissions, newsletters, or AWTRIX scripts.

## Tests
The v1.0.16 account-auth / commissioner / player list / schema tests were run offline with lightweight SDK stubs: 102 passed, seven SDK wire tests were deselected. Python compile and release guard also pass. The live SQL migration, production Streamlit UX, and actual Supabase RPC **must be verified during installation**, because live credentials were not used.
