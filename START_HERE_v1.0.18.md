# Teal's Sunday Pick'em v1.0.18 — All Three Ticker Schedule Editors

**Install over the working v1.0.17 app.** This is a small Commissioner/clock-only
release. It keeps v1.0.17's five-minute-later standings and Caleb 4K Watch,
v1.0.16's required account approvals and account deletion controls, and all
existing scoring, live-refresh timing, linked login, lineups, music, color
fragments, newsletters, backups, and AWTRIX scripts.

## What's new

In the existing app, open **Commissioner → Clock → Edit Broadcast Schedule →
Open Schedule Manager**. There are three independent editors:

| Editor | Hours (Eastern) | Schedule slots | Safety |
|---|---|---|---|
| Saturday Preview | All Saturday | Four, at :00/:15/:30/:45 | Private current-week categories are blocked |
| Sunday Pregame | 10:30 AM until the 1 PM lock | Twelve, every 5 minutes | Private current-week categories are blocked |
| Sunday Live | From the 1 PM lock until midnight | Twelve, every 5 minutes | Live scores, standings and player news are allowed |

All times repeat every hour. For each slot, choose one available message type,
preview the hourly timetable, and press **Save Schedule**. Schedules apply to
future weeks, not just this Sunday's matchup. Only the selected schedule is
saved; other schedules and the separate weekly Commissioner message text stay
as they were. **Reload Saved** discards unsaved slot choices, and **Load
v1.0.17 Default** prepares the original rotation for that editor (you must
still press Save Schedule). Choosing **Off** for a slot skips its message.

There is no new NFL/ESPN refresh or clock polling; these settings only select
which already-prepared content is broadcast. Empty optional categories fall
back to available safe content. The clock token, AWTRIX app configuration,
physical script, and scoring are unchanged.

### The original v1.0.17 timetable is the default

**Saturday** repeats NFL Sunday Preview at :00, :15, :30, and :45.

**Sunday pregame** repeats this privacy-safe 20-minute cycle throughout the
hour: :00 Preview, :05 Commissioner, :10 Readiness, :15 Season, :20 Preview,
:25 Commissioner, :30 Readiness, :35 Season, :40 Preview, :45 Commissioner,
:50 Readiness, :55 Season. The live broadcasts begin after the lock.

**Sunday live** starts with the same twelve slots as v1.0.17:

| Minute | Broadcast | Minute | Broadcast |
|---|---|---|---|
| :00 | NFL Live Scores | :30 | NFL Live Scores |
| :05 | Weekly Standings | :35 | Weekly Standings |
| :10 | Player Update | :40 | Caleb 4K Watch |
| :15 | NFL Live Scores | :45 | NFL Live Scores |
| :20 | Weekly Standings | :50 | Weekly Standings |
| :25 | Season Standings | :55 | Commissioner Message |

Week 1's empty Season Standings can still fall back to Pick'em Pulse; missing
Caleb data still falls back to a regular player update. Nothing about source
freshness is changed here; the separate ticker-lag investigation remains open.

## Installation — follow this order

### 1. Run SQL in the **existing** Supabase project **first**

1. Confirm your installed app says **v1.0.17** and is working normally.
2. Download/open `017_clock_schedule_manager.sql` from this release.
3. Open your **existing** Supabase project → **SQL Editor → New query**.
4. Paste the **entire SQL file**, then press **Run**. It should say Success.
5. **Stop and share the exact error if it fails.** Do not continue to GitHub
   until this step succeeds.

The migration adds three small JSON schedule fields to the existing
`pickem.clock_control` row, constraints preventing pre-lock leaks, and replaces
only the clock feed function. It does **not** delete or recreate the app's
tables, affect the Yahtzee schema, change credentials or player accounts, or
reset your weekly message text. It is safe to rerun. The defaults make the
existing v1.0.17 app continue behaving normally between Steps 1 and 2.

### 2. Upload the browser overlay to GitHub

1. Extract `Teals_Pickem_v1.0.18_BROWSER_UPLOAD.zip` on your Mac.
2. Open your **existing** `teals-sunday-pickem` GitHub repository on **main**.
3. Select **Add file → Upload files**.
4. Drag the **contents of `BROWSER_UPLOAD`**, preserving their folders:
   - At repository root: `app.py`, `config.py`, `store.py`, `gate5_ui.py`, and
     the new `clock_schedule.py`.
   - Under `db/`: new `017_clock_schedule_manager.sql`.
   - Under `tests/`: the included regression tests.
5. Verify that GitHub is **replacing existing files** and placing the new
   ones at the correct paths. There must not be a second `BROWSER_UPLOAD/`
   directory nested inside your repository.
6. Commit to **main** using:
   `v1.0.18 — In-app Saturday and Sunday ticker schedules`

This ZIP is an **overlay, not the whole app**. Keep all other GitHub files.
Do **not** reinstall the AWTRIX script or change clock keys/tokens.

### 3. Verify the release

1. Wait for Streamlit to deploy **v1.0.18** and for **GitHub → Actions →
   Pickem Quality Gate** to pass.
2. Open **Commissioner → Clock → Edit Broadcast Schedule** and check
   **Open Schedule Manager**.
3. Review each schedule. Check **Sunday Live :05, :20, :35, :50 Weekly
   Standings** and **:40 Caleb 4K Watch**.
4. Test saving a harmless edit for one slot, then **Reload Saved** to confirm
   it persisted. Restore the original slot and Save if the edit was only a test.
5. Confirm Saturday and Sunday pregame editors do **not** offer Weekly
   Standings, Player Update, Pick'em Pulse, or NFL Live Scores.
6. Confirm the pre-existing **Test Clock** still works without resetting the
   AWTRIX connection, and the ordinary weekly message controls are intact.

You can edit schedules whenever you like in the future—no SQL or GitHub
changes are required after this one-time installation.

## Problems or rollback

- SQL fails: **stop**, leave GitHub as-is, and send the exact Supabase error.
- The editor says migration 017 is missing: ensure Step 1 ran in the same
  Supabase project used by the app; then reload Streamlit.
- No message at a selected time: confirm it is not set to Off, and note that
  optional content may be unavailable before the weekly snapshot refresh.
- A test edit doesn't show up immediately: the physical clock broadcasts on
  the **next time slot** and will not replay the currently acknowledged slot.
- If the new database logic misbehaves, rerunning
  `db/016_clock_standings_shift_caleb_watch.sql` restores the exact v1.0.17
  hardcoded timetable. New schedule fields may safely remain unused.
- To return the app to v1.0.17 too, revert **only the specific v1.0.18 GitHub
  changes** in a new commit. Do not roll back to v1.0.15, which lacks the
  mandatory v1.0.16 account approval protection.

## Verification completed

- Seven local regression tests covering defaults, privacy allowlists in
  Python and SQL, slot lengths, schedule wiring, and unmodified token/Test
  Clock processing.
- Python compilation and `release_guard.py` completed successfully.
- Inspected the SQL diff against the prior 016 clock function; scoring and
  external refresh code have not been modified.

Full pytest execution and an actual Supabase/AWTRIX end-to-end test were not
available in the build environment. The deployed app and Sunday clock still
need the checks in Step 3.
