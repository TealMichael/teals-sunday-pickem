# v0.4.4 — Gate 4 Navigation Simplification

Gate 4 now uses four non-overlapping top-level destinations:

- **Sunday** — current week, lineup before lock, live/final weekly standings after lock
- **Season** — cumulative season championship standings only
- **History** — prior finalized Sundays
- **Profile** — player stats, trophies, emoji, rules, sign out

The redundant weekly leaderboard view and This Week / Season sub-switch were removed. Existing sessions that were on the old Leaderboard tab migrate to Season automatically. No scoring, NFL-data, lineup, Supabase, auth, or finalization behavior changed.
