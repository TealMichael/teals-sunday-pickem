# v0.2.6 — Gate 2 Performance Pass + Player Card Polish

This release is intentionally the final performance pass before Gate 3 NFL-data work.

## Supabase request audit

The v0.2.5 player-selection path was functionally correct but chatty. A normal selection could cause repeated reads of the same week, player pool, lineup, and picks before the write, followed by the same reads on the Streamlit rerun.

### v0.2.5 steady edit path
A typical existing-lineup selection could involve roughly:
- week + demo-week reads,
- player-pool read in the page shell,
- the same player-pool read again inside the builder,
- lineup read,
- lineup-picks read,
- week validation read,
- player-pool validation read,
- another lineup read before upsert,
- one required lineup-pick upsert,
- then the page rerun repeated most of the reads.

The only database mutation that is fundamentally required for a normal starter change is the lineup-pick upsert.

### v0.2.6 target
After weekly public data is warm and during normal in-session lineup building/editing:
- healthy starter change: **1 Supabase write**,
- emergency-backup change: **1 Supabase write**,
- first-ever pick: **2 writes** (create lineup row + save first pick),
- Save My Lineup: **1 Supabase update**,
- short navigation/reruns after the user's own write use a 12-second session-local lineup snapshot rather than immediately re-reading the same row.

After the short snapshot expires, lineup + all picks are refreshed in **one** PostgREST request rather than separate lineup and lineup-picks requests.

## What changed
- Added short server-process caching for public week/demo-week/player-pool data.
- Player UI fetches only the five visible choices per position; hidden ranks 6–10 remain backend-only.
- Removed the duplicate player-pool read inside lineup views.
- Combined lineup + picks into one nested PostgREST fetch.
- Reused the week, pool, and lineup already loaded on screen when saving a pick.
- Preserved the database trigger as the authoritative lock/eligibility guard.
- Added a short per-browser-session lineup snapshot after successful writes to make the next Streamlit rerun local and fast.
- Added `clear_week_cache()` for Gate 3/Commissioner data refreshes to invalidate public-data caches immediately when needed.

## UI polish
- QUESTIONABLE / OUT status badges now sit inline beside the player name.
- The whole player card remains the one-tap selection target via an invisible full-card Streamlit button overlay.

## Safety preserved
- Autosave remains authoritative in Supabase; picks are not browser-only.
- Database `guard_lineup_pick` trigger still enforces opening/lock time, weekly pool membership, position, visibility, and OUT restrictions.
- Local lineup snapshots are short-lived and player/week-specific.
- No Gate 1 auth/session behavior changed.
