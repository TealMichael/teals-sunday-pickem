# v0.4.2 — Gate 4 Navigation + Leaderboard Polish

- Replaces the nested Streamlit leaderboard tabs with a session-state-backed This Week / Season switch so the selected view survives reruns.
- Fixes leaderboard drill-down behavior: tapping a player now opens their roster immediately beneath that player instead of after the entire standings list.
- Tapping the same player again closes the detail.
- Polishes the sticky Sunday / Leaderboard / History / Profile navigation into a clearer mobile app bar.
- Polishes leaderboard rows, season standings, demo history, demo profile, and Sunday Storylines.
- Makes Sunday Storylines responsive on phones and clarifies the Went Alone overflow text.
- No database, scoring, NFL-data, or authentication changes.
