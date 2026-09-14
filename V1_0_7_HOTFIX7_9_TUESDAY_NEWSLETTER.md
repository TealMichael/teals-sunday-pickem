# Teal's Sunday Pick'em — v1.0.7 Hotfix 7.9
## Tuesday Text Newsletter

Adds a Commissioner-only Tuesday newsletter generator designed for copy/paste into a group text.

### Newsletter content
- Full final standings for the most recently finalized week, compacted onto one line.
- Perfect 5 from the actual visible 25-player pool, plus the perfect score.
- Current season leader (co-leaders supported).
- Direct link to the currently open next-week lineup.

### Commissioner workflow
A new **Newsletter** tab appears in Commissioner mode. The app reads finalized data automatically, generates the message, shows a character/SMS estimate, lets the Commissioner edit the text, and provides a one-tap copy button.

The public Pick'em link is auto-detected when possible. It can be corrected and saved once; the saved link is stored in the existing `pickem.app_meta` table, so no database migration is required.

### Safety / scope
- Nothing is sent automatically.
- No phone numbers or recipient information are stored.
- No changes to picks, scoring, player pools, Sunday ticker logic, NFL refresh cadence, lock behavior, or AWTRIX.
- No Supabase SQL migration required.

### Validation
- Full pytest suite: **262 passed**
- Python compilation: PASS
- release_guard.py: PASS
