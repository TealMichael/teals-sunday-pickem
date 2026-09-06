# Teal's Sunday Pick'em — Gate 4 Live Sunday + Season

Version: **v0.4.0**

Gate 4 layers the social/live experience on top of the green Gate 1–3.5 foundations. It does not change PIN/session authentication, weekly pick saving, provider adapters, scoring rules, or the Gate 3.5 real-box-score path.

## What Gate 4 adds

- Four-tab player navigation: **Sunday / Leaderboard / History / Profile**
- Sunday tab transforms after the 1:00 PM ET lock into live/final standings
- Full-row tappable weekly leaderboard with `← YOU` identification and a pinned own-rank strip
- Tap any player after lock to see their five, per-player points, game status, and scoring breakdown
- Emergency backups remain private unless activated; the logged-in user may still see their own stored emergency
- Sunday Storylines: **Most Popular Pick / Went Alone / Same Brain**
- Weekly traditional-competition ties
- Season point system: **12–9–7–6–5–4–3–2–1**, 10th+ = 0
- Season standings sorted by season points, then total fantasy points
- Finalized weekly history with compact result rows
- Profile trophies/stats, emoji editing, How to Play, Trophy Case placeholder/archive
- Full-screen 2–3 second football-flood champion/co-champion celebration after Monday finalization
- Monday final page includes season leader + user's season position
- Final weekly results archive before detailed rosters are removed
- Detailed rosters purge only after the following Tuesday player pool successfully publishes
- Week 18 season champion/co-champion archive

## Gate 4 database migration

Run `db/004_gate4_live_social.sql` in Supabase SQL Editor after Gate 3.

Then expose these two new Pick'em tables in **Integrations → Data API → Settings → Exposed tables**:

- `pickem.weekly_results`
- `pickem.season_champions`

No new Streamlit secrets or GitHub Actions secrets are required.

## Gate 4 demo mode

Commissioner mode now has **Preview Gate 4 Live Sunday Demo**. It uses only in-memory synthetic players/lineups/scores and never writes to Week 1.

Acceptance flow:

1. Open Commissioner → **Preview Gate 4 Live Sunday Demo**.
2. Verify Sunday Storylines and the live weekly leaderboard.
3. Tap leaderboard rows; verify five-player roster drill-down and scoring detail.
4. Check the four navigation tabs.
5. Choose **Final Demo** and verify the co-champion football flood, tied ranking, and season-point preview.
6. Check Profile / How to Play / Trophy Case presentation.
7. Exit Demo and confirm real Week 1 remains unchanged.

Gate 4 should not be marked GREEN until this deployed demo is accepted on both desktop and phone.

## Data-retention contract

After Monday reconciliation, Gate 4 writes compact `weekly_results` rows: final rank, nickname/emoji snapshot, weekly score, season points earned, champion state. When the next Tuesday pool successfully publishes, the prior week's `lineups` are deleted (and `lineup_picks` cascade), preserving only compact history.

## Tests

- `90 passed`
- `python -m compileall` PASS
- `release_guard.py` PASS
