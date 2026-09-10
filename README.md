# Teal's Sunday Pick'em

Current build: **v1.0.6 — Automation Hardening**

## Release status
- Gate 1 — player identity, PIN auth, remembered devices ✅
- Gate 2 — weekly five-player game and emergency backups ✅
- Gate 3 — NFL schedule/player/injury/scoring pipeline ✅
- Gate 3.5 — real preseason + Wednesday live-game production rehearsal ✅
- Gate 4 — Sunday experience, season standings, history, profile ✅
- Gate 5 — Commissioner controls ✅
- Gate 6 — launch readiness, rehearsal, heartbeat, CI quality gate ✅

## v1.0 live cadence
GitHub Actions remains the primary shared backend worker. Sunday injury checks run every 15 minutes beginning in the 11 AM ET window. After the universal 1:00 PM ET lock, the same cadence powers live score refreshes through the late-Sunday/SNF window. Weekday injury checks remain intentionally sparse.

v1.0.6 adds a guarded second layer for the launch-critical moments where GitHub scheduled jobs have proven they can arrive late. When an authenticated player is on the Sunday tab and the relevant backend job is overdue, the Streamlit server may recover Tuesday publication, the final two-hour injury/status window, Sunday live scoring, or Monday final reconciliation. A short server-only Supabase lease ensures concurrent users do not all run the same provider refresh.

Normal fresh page views do not poll providers. The fallback is stale-only, rate-limited, and non-fatal. The Wednesday full-game rehearsal's scoring/parser/matching code remains unchanged.

## One-time v1.0.6 database step
Run `db/005_automation_hardening.sql` once in the Supabase SQL Editor. Until that migration is applied, the app simply leaves recovery to GitHub/manual Commissioner controls.
