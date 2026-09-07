# v0.4.5 — Season Standings Hard Cleanup

- Removes any lingering Gate 4 weekly-leaderboard sub-tab state.
- Makes the second top-level destination explicitly **Season Standings**.
- Adds a Streamlit deployment guard so an older Gate 4 UI module cannot survive a multi-file deploy.
- Keeps Sunday as the only home for current-week live/final standings.
- No scoring, NFL data, Supabase, lineup, or season-point logic changes.
