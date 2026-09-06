# Gate 3 — NFL Data (v0.3.0)

Gate 3 connects the proven Gate 1/2 app to real NFL data without changing the player-facing lineup architecture.

## What Gate 3 adds

- Real NFL schedule normalization and strict Sunday eligibility: only Sunday games beginning at 1:00 PM ET or later.
- One-time 2026 Week 1 consensus ranking seed for QB/RB/WR/TE, filtered against the live eligible schedule.
- Week 1 kickers selected from the strongest implied offenses when current odds are available; deterministic offense fallback if odds are unavailable.
- Week 2+ in-house ranking: 55% season Pick'em PPG + 30% last-three PPG + 15% workload. Matchup strength is never an input.
- Sleeper player/injury cache with HEALTHY / QUESTIONABLE / OUT normalization.
- Increasing injury-refresh cadence as Sunday approaches.
- Before Saturday 11:59 PM ET: visible OUT players are replaced by the next eligible hidden rank; affected starters are removed from lineups so users must choose again.
- After Saturday 11:59 PM ET: injury status can change, but the five-player pool stays frozen.
- Schedule changes are different: a game moved outside the Sunday eligibility window before lock makes those players ineligible and promotes replacements even after the normal injury freeze.
- ESPN live box-score adapter for 30-minute Sunday scoring snapshots.
- nflverse Monday reconciliation before scores become FINAL.
- Flat kicker scoring: any made FG = 3, XP = 1, misses = 0.
- Manual-score-override columns are reserved now so future Commissioner tools can remain authoritative.
- Automatic next-week shell creation after Monday finalization.
- Data-run audit trail for scheduled jobs and future Commissioner health/status UI.

## Free / replaceable provider design

The provider boundary lives in `nfl_sources.py`:
- `ESPNProvider`: schedule / game status / convenience live box scores. This is treated as an undocumented convenience source and can be replaced.
- `SleeperProvider`: free noncommercial player and injury metadata; calls are shared/cached in the backend, never made by each phone.
- `NFLverseProvider`: weekly/final statistics and Week 2+ historical inputs.

No paid FantasyPros or SportsDataIO API is a production dependency. Week 1 public fantasy rankings are used only to establish the one-time seed order.

## Automation

`.github/workflows/nfl-refresh.yml` runs a lightweight shared backend job every 30 minutes from 7 AM–midnight ET, plus 12:00/12:30 AM for a long Sunday night game. The Python auto-run decides whether anything is actually due.

Typical cadence:
- Tue–Thu injury cache: every 6 hours
- Fri: every 4 hours
- Sat: every 3 hours
- Sun 8–11 AM: hourly
- Sun 11 AM–1 PM: every 30 minutes
- Sun after 1 PM: injury check hourly; scoring check every 30 minutes
- Monday 9 AM+: retry nflverse reconciliation until settled

GitHub Actions is used because the repo is public and standard public-repo runners are free. GitHub can disable scheduled workflows after 60 days without repository activity; Gate 5/7 should surface scheduler freshness so this cannot fail silently.

## Important Gate boundary

Gate 3 stores live/provisional/final player scores and scoring breakdowns. The friend leaderboard, roster drill-down, storylines, weekly placement points, and winner experience remain Gate 4.
