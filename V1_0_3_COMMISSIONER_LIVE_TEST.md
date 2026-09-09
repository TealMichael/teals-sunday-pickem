# v1.0.3 Commissioner Live Game Dress Rehearsal

## Purpose
Add a safe Wednesday-night production-data rehearsal before the first real Sunday.

## Scope
Commissioner → Diagnostics only. Public signup, lineup building, Sunday Status, standings, scoring persistence, Week 1 pool, and friend-facing screens are unchanged.

## New diagnostic
**Wednesday Live Game Dress Rehearsal**

1. Load the real current-week NFL schedule from nflverse.
2. Choose the Wednesday night game.
3. Run the test after kickoff.
4. The diagnostic reads the real ESPN CDN box score.
5. It runs the same ESPN player-stat parser used by production live scoring.
6. It matches ESPN players to the cached Sleeper identities using the same team + normalized-name key used by production.
7. It scores those stat lines with the production `score_stat_line()` formula.
8. It shows sample QB/RB/WR/TE/K totals with the raw scoring ingredients and point math.
9. Re-running the test compares the new snapshot to the previous one and reports how many stat lines changed.

## Safety
The rehearsal is deliberately read-only. It does **not** write:
- Week 1 player scores
- player lineups
- standings/results
- player pool rows
- NFL schedule rows
- Week 1 data status/freshness
- Commissioner activity

The only Supabase access is a read of the already-cached NFL player identities for cross-provider matching.

## Wednesday success target
- Game status moves to LIVE.
- ESPN player rows parse successfully.
- QB/RB/WR/TE/K scoring rows appear.
- Cached Sleeper identity match rate remains healthy (warning below 85%).
- Fantasy totals and raw stat ingredients change across repeated snapshots.
- Displayed scoring math agrees with the live box score.

## Verification
- pytest: 156/156 PASS
- Full Week Rehearsal: 9/9 PASS
- compileall: PASS
- release_guard: PASS
