# Teal's Sunday Pick'em

Current build: **v1.0.4 — Public UX Polish**

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

v1.0.4 keeps the proven v1.0.3 live-scoring and lineup behavior intact while polishing two player-facing moments: first-time onboarding now explains the core scoring rules, and the Review My Five screen places SAVE MY LINEUP before secondary edit controls. Full rules remain available under Profile → How to Play & Scoring.

No SQL migration, Supabase setting, workflow change, or new secret is required for v1.0.4.
