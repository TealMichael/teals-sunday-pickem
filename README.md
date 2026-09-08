# Teal's Sunday Pick'em

Current build: **v1.0.3 — Pick Confirmation + Publish Reliability**

## Release status
- Gate 1 — player identity, PIN auth, remembered devices ✅
- Gate 2 — weekly five-player game and emergency backups ✅
- Gate 3 — NFL schedule/player/injury/scoring pipeline ✅
- Gate 3.5 — real preseason production replay ✅
- Gate 4 — Sunday experience, season standings, history, profile ✅
- Gate 5 — Commissioner controls ✅
- Gate 6 — launch readiness, rehearsal, heartbeat, CI quality gate ✅

## v1.0 live cadence
The backend uses one shared GitHub worker for all players. Sunday injury checks run every 15 minutes beginning in the 11 AM ET window. After the universal 1:00 PM ET lock, the same cadence powers live score refreshes through the late-Sunday/SNF window. Weekday injury checks remain intentionally sparse.

v1.0.3 keeps the v1.0.2 Sunday confidence/weekly recap experience and adds two launch-polish changes: deliberate Select → highlight → Next lineup navigation, plus a redundant Tuesday-noon publication retry window. Scoring, player rankings, lock rules, emergency-backup activation, database schema, and authentication are unchanged.

No SQL migration, Supabase setting, or new secret is required for v1.0.3.
