# v1.0.5 — Tap-to-Edit Lineup Review

## What changed
- The five Review My Five player cards are now native full-card tap targets.
- Tapping a card opens that exact position for editing.
- The saved player is already highlighted when the picker opens.
- After the replacement is confirmed, the flow returns directly to Review My Five.
- Removed the separate “Need to make a change?” section and Change QB/RB/WR/TE/K buttons.
- SAVE MY LINEUP remains the primary action immediately below the five cards.
- Questionable-player emergency backup context remains visible on the review card.
- OUT-player review cards remain tappable so an unavailable starter can be replaced directly.

## Safety scope
This release does not change scoring, NFL ingestion, player-pool selection, lineup persistence, Supabase schema, auth, Sunday lock rules, Commissioner diagnostics, or GitHub Actions.

## Verification
- pytest: 172/172 PASS
- Full Week Rehearsal: 9/9 PASS
- Python compile: PASS
- release_guard: PASS
