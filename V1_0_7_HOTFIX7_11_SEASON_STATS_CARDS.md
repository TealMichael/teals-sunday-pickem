# Teal's Sunday Pick'em — v1.0.7 Hotfix 7.11 — Season Stats on Pick Cards

Build tag: `v1.0.7-hotfix7.11`

## Player-facing change

The existing full-size, one-tap player card now has a small muted statistical strip directly underneath the player name/team/matchup. The three position-specific stats are:

- QB: passing yards/game, season passing touchdowns, rushing yards/game.
- RB: rushing yards/game, receiving yards/game, season total touchdowns.
- WR / TE: receiving yards/game, receptions/game, season total touchdowns.
- K: made field goals, made extra points, FG percentage.

Each card also notes the count of weeks with a recorded player stat line (`GP`). The builder explains that yard/catch averages use recorded games, and touchdown/kick totals are seasonal. Stats include **only regular-season weeks earlier than the current Pick'em week**. `Season stats pending` is shown where the source hasn't supplied a safe match; missing data is never mislabeled as zero. The demo picker keeps its original cards.

## Data and safety

Uses the existing nflverse full-season weekly CSV (already used by the ranked-pool builder), without requesting per-player ESPN box scores. On the first real picker/review view after deploy, one Streamlit session acquires the existing Supabase refresh lease, retrieves the weekly CSV once, builds a snapshot for the **full frozen pool including hidden reserves**, and saves one JSON entry in existing `pickem.app_meta`. Other sessions read the shared snapshot. A temporary failure is suppressed and retried after a shared 20-minute cooldown; lineups remain available. All stats remain frozen for that week, including during Sunday's live scoring. Week 1 has no prior-season stats.

This module has no code path that updates `player_pool`, `lineup_picks`, injury status, scoring, pool rankings, or lock behavior. No new database tables, AWTRIX changes, workflow changes, paid services, or secrets are required.

## Verification

Automated local reconstructed-7.10.1 baseline: 279 tests passed, Python compilation passed, release guard passed. Unit tests include QB/RB/WR/TE/K calculations, FG accuracy zero attempts, REG/current-week filtering, recorded-game averaging, duplicate week handling, hidden replacements, provider failure cooldown, shared lease, and read-only behavior. **Live 2026 provider and Supabase data were not accessible in this build environment**; confirm actual Week 2 card values in Streamlit after deployment. Unmatched/missing player stats will show pending rather than an invented number.
