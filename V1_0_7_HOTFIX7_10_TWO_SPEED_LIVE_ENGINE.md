# Teal's Sunday Pick'em — v1.0.7 Hotfix 7.10
## Two-Speed Live Sunday Engine

### What changes
- Adds a leased active-user live lane after the 1:00 PM ET lock.
- Lightweight NFL game score/quarter/clock state can refresh about every 2 minutes while at least one Sunday screen is open.
- Pick'em fantasy-player stats can refresh about every 3 minutes while at least one Sunday screen is open.
- Sunday standings reread shared Supabase data every 15 seconds.
- GitHub Actions remains the durable unattended 5-minute live-scoring worker.
- The existing recovery layer remains available if the fast lane and GitHub fall behind.
- Stale live game clocks older than 7 minutes no longer pretend to be current. The last confirmed score remains visible, but the quarter/clock collapses to LIVE until a fresh state arrives.

### Load / safety design
- Supabase refresh leases ensure many open phones still produce one shared provider refresh, not one provider request stream per user.
- The heavier player-stat lane also refreshes game state from the same ESPN summaries, so the app avoids a redundant lightweight call in that cycle.
- Failed active game-state attempts cool down for 1 minute; failed active player-stat attempts cool down for 2 minutes.
- If ESPN's lightweight scoreboard surface is unavailable, the 3-minute CDN summary lane and 5-minute GitHub worker continue to provide live data.

### Unchanged
- Pick'em scoring rules
- Player pools and saved lineups
- Emergency backups
- Sunday 1:00 PM lock
- Tuesday publication
- Monday final reconciliation
- AWTRIX 15-second device poll
- AWTRIX content cadence / ticker schedule
- GitHub's 5-minute Sunday background schedule

### Install
Upload the contents of `UPLOAD_TO_GITHUB` to the repository root and commit.

No Supabase SQL is required.
No AWTRIX reinstall is required.
No GitHub workflow replacement is required.

### Validation
- `pytest -q`: 269 passed
- Python compilation: passed
- `release_guard.py`: passed
