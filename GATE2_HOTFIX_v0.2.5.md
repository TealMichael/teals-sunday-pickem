# v0.2.5 — Gate 2 Injury Badge Card Fix

- Keeps the yellow QUESTIONABLE (and OUT) status badge inside the same visual player-selection card as the player name and matchup.
- Preserves one-tap selection, selected checkmarks, autosave, edit return-to-review behavior, and emergency-backup logic.
- Uses a keyed bordered Streamlit container plus a full-width tertiary button so the card has only one visible border.
- No database migration, Supabase setting, or secret change is required.
