# Teal's Sunday Pick'em v1.0.17 — Ticker Schedule + Caleb 4K Watch

This is a **clock-only** update over the installed v1.0.16. It preserves the
commissioner-approval account controls, linked login, scoring, lineups,
background refresh timing, Saturday preview, Sunday pre-lock privacy,
Commissioner messages/melodies, and your physical AWTRIX script.

## What's changing

| Minutes after the hour | Sunday after the 1 PM ET lock |
|---|---|
| :00 | NFL LIVE scores |
| :05 | Full current-week Pick'em standings |
| :10 | Pool-player update |
| :15 | NFL LIVE scores |
| :20 | Full current-week Pick'em standings |
| :25 | Season standings (Pulse when unavailable) |
| :30 | NFL LIVE scores |
| :35 | Full current-week Pick'em standings |
| :40 | Caleb 4K Watch; normal player update if unavailable |
| :45 | NFL LIVE scores |
| :50 | Full current-week Pick'em standings |
| :55 | Enabled Commissioner message |

The four standings broadcasts are now five minutes later. To keep Caleb
**exactly at :40** as approved and preserve four NFL-score messages per hour,
the four NFL-score slots move five minutes earlier. Everything else keeps its
previous slot. This changes **display timing only**, not score retrieval.

Caleb Watch shows passing yards today when playing on Sunday, season yards,
yards to 4,000, and projected 17-game pace. Its extra data is requested only by
the scheduled GitHub worker; the active Streamlit scoring worker continues
using saved data without an extra ESPN request. If external Caleb stats fail,
the snapshot keeps the previous good watch, and an unavailable watch falls back
to a regular player update.

## Install, in this order

### 1. Supabase — run the new SQL first

1. Confirm the **existing v1.0.16** app and account approval controls are working.
2. In the **same existing Supabase project**, open **SQL Editor → New query**.
3. Open `db/016_clock_standings_shift_caleb_watch.sql` from this release.
4. Paste its **entire contents**, then click **Run**. It must report Success.
5. **STOP if the SQL fails.** Do not upload the Python update until the SQL succeeds.

The SQL only replaces `pickem.clock_feed`. It does **not** create/drop tables,
change scores, alter accounts, modify lineups, or affect the shared Yahtzee
schema. It is safe to rerun if the first run succeeded. During the brief time
before GitHub is updated, the :40 slot falls back to an ordinary player update.

### 2. GitHub browser upload — use the overlay folder

1. Extract `Teals_Pickem_v1.0.17_BROWSER_UPLOAD.zip` on your Mac.
2. Open the existing `teals-sunday-pickem` GitHub repository on **main**.
3. Choose **Add file → Upload files**.
4. Drag the **contents** of the `BROWSER_UPLOAD` folder into GitHub. The root
   files `app.py`, `config.py`, and `gate5_ui.py` must be at the repository root;
   `scripts/nfl_refresh.py`, `db/016_clock_standings_shift_caleb_watch.sql`,
   and the `tests/` files must retain their subfolders. Do **not** upload an
   enclosing `BROWSER_UPLOAD` folder inside your repository.
5. Commit with the message: `v1.0.17 — Ticker standings shift and Caleb 4K Watch`.
6. Do **not** delete or replace unrelated repository files. This overlay
   contains only changed/new files, not a full replacement of the repository.

### 3. Confirm deployment and prime Caleb data

1. Wait for Streamlit to show **v1.0.17** and GitHub **Actions → Pickem Quality
   Gate** to pass.
2. In GitHub, open **Actions → Pickem NFL Refresh → Run workflow**. Use branch
   `main`, mode `auto`, week `0`, force `false`. Run it once to build the
   current week's optional Caleb snapshot. The normal scheduled refreshes
   will also do this; this manual run is just a pre-Sunday check.
3. Confirm the workflow succeeds. Then open the app's **Commissioner → Clock →
   Preview automatic rotation**. It now includes a **Caleb 4K Watch** sample
   when the external season data was available.
4. The existing physical clock script **does not need updating**. Do not
   change the Supabase URL, publishable key, or clock token.

### 4. Sunday verification

1. Before 1 PM ET, the ticker must still show privacy-safe pregame content;
   no current-week picks or weekly standings may appear before the lock.
2. After the lock, watch for **standings at :05/:20/:35/:50**, **Caleb at :40**,
   and **NFL scores at :00/:15/:30/:45**.
3. For the separate freshness investigation, compare the app's Live Sunday
   standings with **Commissioner → Clock → Preview automatic rotation**, and
   note the snapshot update age. Avoid pressing **Refresh Clock Preview**
   during that comparison, as it would mask a lagging automatic refresh.

## If anything goes wrong

- If SQL fails, stop before the browser upload and send the exact SQL error.
- If Caleb's provider is unavailable, the ordinary game can continue; the
  watch is optional and uses a normal player update as its fallback.
- To revert the **clock schedule only**, rerun the previous
  `db/013_pregame_four_way_double_scroll.sql` from v1.0.16. That restores the
  old standings/scores slots and parks Caleb without touching player accounts.
- To return the app display/version and GitHub scheduled worker to v1.0.16,
  revert this release's **specific GitHub file changes** with a new commit.
  **Never roll back to v1.0.15**, which does not enforce the new-account
  approval policy introduced in v1.0.16.

## Verification completed before delivery

- Six isolated v1.0.17 smoke checks, including Caleb season/live math and
  the complete Sunday post-lock timetable.
- Python compilation of all changed `.py` files.
- `release_guard.py` for missing files and accidental secret literals.
- Historical SQL comparison: Saturday and Sunday pre-lock branches are
  unchanged by this migration.

Full pytest execution and a live Supabase/AWTRIX test were not possible in the
offline build workspace. Sunday production behavior still needs observation.
