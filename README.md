# Teal's Sunday Pick'em

**Build:** v0.3.0 — Gate 3 NFL Data

A small friends-only Sunday fantasy football pick'em built with Streamlit + Supabase.

## Gate status

- **Gate 1 — Foundation:** GREEN. Secure nickname/PIN accounts, season-long remembered login, second-device login, Commissioner auth.
- **Gate 2 — Weekly Game:** GREEN. Tuesday open, QB/RB/WR/TE/K lineup builder, autosave, stable shuffle, Questionable emergency backups, review/edit/save, Sunday 1 PM ET lock, and performance pass.
- **Gate 3 — NFL Data:** BUILT / awaiting deployed provider acceptance. Real NFL schedule, Week 1 pool generation, Week 2+ ranking algorithm, injuries, live scoring ingestion, Monday reconciliation, and scheduled backend refresh.

## Gate 3 source strategy

- Sleeper: free noncommercial player/injury metadata.
- ESPN site data: replaceable convenience adapter for schedule/live game summaries.
- nflverse: weekly/final player stats and Week 2+ historical inputs.
- No paid fantasy API is required for production.

See `DEPLOYMENT_STEPS.txt`, `GATE3_BUILD_NOTES.md`, and `GATE3_TEST_REPORT.txt`.
