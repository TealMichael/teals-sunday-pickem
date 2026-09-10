# v1.0.3 Live Test Cache Pagination Hotfix

## What we found during Wednesday live testing
The identity diagnostic reported exactly **1000 cached fantasy players** and then failed to find obvious current players such as Sam Darnold and Jaxon Smith-Njigba. The diagnostic was using one unfiltered Supabase select for `nfl_players`; that read can be capped at 1000 rows.

## Fix
The Commissioner-only live rehearsal now loads the cached fantasy roster by the five fantasy positions (QB/RB/WR/TE/K) and deduplicates the results. Each position-specific read is below the row cap, so the diagnostic sees the full relevant cache.

This does **not** change production Sunday matching, live scoring, the public app, player pools, lineups, standings, SQL, or GitHub workflows.

## Verification
- 162/162 pytest tests PASS
- Full Week Rehearsal 9/9 PASS
- Python compile PASS
- release_guard PASS
