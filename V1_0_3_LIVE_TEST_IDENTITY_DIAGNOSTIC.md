# v1.0.3 — Live Test Identity Diagnostic Hotfix

## Scope
Commissioner-only, read-only follow-up to the Wednesday live-game rehearsal. No production scoring rule or player-facing flow is changed.

## What it adds
When a live scoring row does not match the exact production `team + normalized name` key, Commissioner → Diagnostics now shows **Why unmatched?** with:
- ESPN player, team, inferred role, and ESPN athlete ID
- the exact reason the production key missed
- same-name cached players on another team (stale-team clue)
- close same-team cached name candidates (name-variation clue)
- cached Sleeper player ID / position / name similarity
- cache size and latest sync age
- the live scoring stats attached to the unmatched ESPN row

The diagnostic deliberately does **not** change production matching. Its purpose is to identify the safest hardening rule before Sunday rather than guessing during a live game.

## Protected surfaces unchanged
- production `nfl_sync.py`
- scoring formulas
- `store.py`
- player pool / lineups / public Sunday UI
- auth / PINs
- SQL migrations
- GitHub workflows

