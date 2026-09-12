# v1.0.7-hotfix5 — Sunday Clock NFL Score Cadence

## Change
The post-lock AWTRIX rotation now gives live NFL scores a dedicated slot every 15 minutes:

- :00 — weekly Pick'em standings
- :05 — NFL LIVE scores
- :10 — Pick'em-pool Player Update
- :15 — weekly Pick'em standings
- :20 — NFL LIVE scores
- :25 — Pick'em Pulse in Week 1 / Season standings in Week 2+
- :30 — weekly Pick'em standings
- :35 — NFL LIVE scores
- :40 — Pick'em-pool Player Update
- :45 — weekly Pick'em standings
- :50 — NFL LIVE scores
- :55 — optional Commissioner message

## Preserved
- Pregame privacy before the 1:00 PM ET lock is unchanged.
- The physical AWTRIX still polls every 15 seconds on Sunday and deduplicates event IDs.
- NFL-data refresh jobs remain on their existing cadence; this hotfix changes airtime, not provider polling.
- Scoring, lineups, pool immutability, injury status, auth, and lock timing are untouched.
- The public RPC wrapper and pgcrypto search-path repairs from the clock hotfix remain in place.

## Install
After the GitHub patch is deployed, run `db/008_clock_nfl_score_cadence.sql` once in Supabase SQL Editor. No AWTRIX script replacement is required.
