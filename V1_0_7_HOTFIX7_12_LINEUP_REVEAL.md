# v1.0.7 Hotfix 7.12 — 1 PM Lineup Reveal

A read-only Sunday kickoff reveal derived from the current week's existing Supabase public bundle. No schema changes and no extra NFL requests.

- Appears on Sunday after the existing 1:00 PM ET lineup lock, above the live storylines and standings. Not shown to players while picks are still open, in demo mode, or on the final Monday recap.
- Compact kickoff summary shows participating lineups, fully filled lineups, a crowd pick, solo-pick count, and Same Brain group count.
- Expand **See who picked whom — all five positions** to see the starters and the nicknames who chose each one, with counts and solo-player callouts. Identical lineups require all five matching starter IDs.
- Displays locked starters, not unactivated emergency backups. Unknown pool IDs receive a neutral display label, not an internal ID. All names in HTML are escaped.
- No changes to saved picks, eligibility, ranking, scoring, emergency backups, refresh cadence, GitHub workflows, or clock.

**Deployment**: Upload the files in the visible `UPLOAD_TO_GITHUB` folder to the repository root on `main` after the already-installed Hotfix 7.11. No SQL to run. No AWTRIX reinstall.

**Commit**: `v1.0.7 hotfix — add 1 PM lineup reveal`
**Tag**: `v1.0.7-hotfix7.12`

**Validation**: 285 local tests passing; syntax compilation and release guard passing. Sunday production view needs visual confirmation after 1 PM ET. The early-week picker should not expose group choices.
