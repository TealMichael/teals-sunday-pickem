# v1.0.0 — Week 1 Release

Teal's Sunday Pick'em is launch-ready for the 2026 regular season.

## Locked release behavior
- Five-player weekly lineup: QB / RB / WR / TE / K.
- Tuesday noon ET player-pool opening.
- Universal Sunday 1:00 PM ET lock.
- Sunday-only eligible games beginning at 1:00 PM ET or later.
- Half-PPR fractional scoring and flat 3-point made field goals.
- Questionable-player emergency backups.
- Live Sunday standings, roster drill-down, storylines, season standings, history, profile trophies, and champion celebration.
- Commissioner PIN reset, protected pool correction, manual score override, NFL refresh, diagnostics, and launch-readiness tools.
- Real NFL box-score replay verified end-to-end through the production GitHub worker.
- CI quality gate, automation heartbeat, friendly runtime recovery, and launch rehearsal.

## Final Sunday cadence
- Tue-Thu: approximately every 6 hours.
- Friday: approximately every 4 hours.
- Saturday: approximately every 3 hours.
- Sunday 8-11 AM ET: hourly.
- Sunday 11 AM ET through late night: every 15 minutes for injury/status updates.
- Sunday 1 PM ET through the late-SNF/overtime buffer: every 15 minutes for live scoring.
- Monday morning: hourly reconciliation retries beginning shortly after 9 AM ET until the scheduled retry window ends.

GitHub cron entries use a +7 minute offset (and +22/+37/+52 for quarter-hour runs) to reduce top-of-hour scheduling congestion.

## Deferred by design
Web Push notifications remain post-launch. Week 1 does not depend on notification permissions or service-worker behavior.

## v1.0.6 — Automation Hardening
After real Week 1 rehearsal exposed multi-hour delays in GitHub scheduled-job start times, v1.0.6 keeps GitHub as the primary scheduler and adds a stale-only Streamlit fallback for launch-critical windows. A server-only Supabase lease prevents duplicate concurrent refreshes. The fallback covers delayed Tuesday publication, the final two hours of Sunday injury/status checks, Sunday live scoring, and Monday final reconciliation. The production scoring/parser/matching engine validated in the Wednesday full-game rehearsal is unchanged.

## v1.0.7 — Sunday Clock Broadcast + Commissioner Cleanup
- Added optional Sunday-only AWTRIX broadcast feed with hashed scoped token.
- Added Commissioner Clock tab with three week-specific optional messages and Test Clock.
- Automatic clock content: full weekly standings, all live NFL scores, 25-player-pool-only Player Updates, Pick'em Pulse, and Week 2+ full season standings.
- Pre-lock feed never reveals picks or standings.
- Consolidated launch/recovery/build diagnostics into one Diagnostics tab.
- Proven NFL live scoring/parser/matching engine and GitHub workflows unchanged.
