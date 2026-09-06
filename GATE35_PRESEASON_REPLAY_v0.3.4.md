# v0.3.4 — Gate 3.5 Real Preseason Replay

Adds a Commissioner-only acceptance test that reads the completed 2026 Chicago Bears at Tennessee Titans preseason box score from ESPN, validates independently known stat anchors, maps real QB/RB/WR/TE/K stat lines through the production parser and scoring engine, round-trips them through Supabase using hidden Gate 2 Test Week players, proves Week 1 is untouched, and restores the test state afterward.

No SQL, Supabase setting, Streamlit secret, or GitHub Actions secret changes are required.
