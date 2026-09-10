# Teal's Sunday Pick'em

Current build: **v1.0.7 — Sunday Clock Broadcast + Commissioner Cleanup**

## Release status
- Gate 1 — player identity, PIN auth, remembered devices ✅
- Gate 2 — weekly five-player game and emergency backups ✅
- Gate 3 — NFL schedule/player/injury/scoring pipeline ✅
- Gate 3.5 — real preseason + full Wednesday live-game production rehearsal ✅
- Gate 4 — Sunday experience, season standings, history, profile ✅
- Gate 5 — Commissioner controls + Sunday Clock ✅
- Gate 6 — launch readiness, rehearsal, heartbeat, CI quality gate ✅

## v1.0 live cadence
GitHub Actions remains the primary shared backend worker. Sunday injury checks run every 15 minutes beginning in the 11 AM ET window. After the universal 1:00 PM ET lock, the same cadence powers live score refreshes through the late-Sunday/SNF window. v1.0.6's guarded fallback remains available if GitHub scheduled jobs are late.

## Sunday Clock
v1.0.7 adds an optional AWTRIX broadcast layer. The clock never calculates fantasy results itself; it reads compact, safe display messages generated from Pick'em's stored source-of-truth data.

Normal Sunday broadcast begins around 10:30 AM ET and ends at midnight. Before lock it keeps picks private. After lock it rotates full weekly standings, all currently live NFL game scores, Player Updates drawn only from the week's 25 visible Pick'em players, Pick'em Pulse items, and (starting Week 2) the full season standings. Three optional Commissioner messages are stored per week, so stale party names/messages do not carry into the next Sunday.

The AWTRIX client is a separate headless script and does not replace the existing school Class Schedule or Fact Challenge clock scripts.

## Commissioner
Top-level Commissioner navigation is intentionally simple:

**Week • Players • Corrections • Clock • Diagnostics**

Launch/readiness checks, database/run history, live-game rehearsal, and legacy build diagnostics are consolidated under Diagnostics.

## One-time v1.0.7 setup
1. Run `db/006_sunday_clock.sql` once in Supabase SQL Editor.
2. Open Commissioner → Clock and generate a scoped Clock Token.
3. Install `awtrix/PickemSunday.ax` on AWTRIX as a separate script.
4. Configure it with the Supabase URL, Supabase publishable/anon key, and scoped Clock Token.
5. Use Commissioner → Clock → Test Clock before Sunday.

Never place the Supabase service-role/secret key on the physical clock.
