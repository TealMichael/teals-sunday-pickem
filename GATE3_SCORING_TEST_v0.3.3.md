# v0.3.3 — Gate 3 Scoring Diagnostic

Adds a Commissioner-only **Run Gate 3 Scoring Test** acceptance test.

The diagnostic:
- uses hidden players from the isolated Gate 2 Test Week only;
- verifies QB, RB, WR, TE, and K controlled scoring scenarios;
- covers fractional half-PPR, passing/rushing/receiving scoring, interceptions, fumbles, two-point conversions, trick-play passing, return TDs, and flat 3-point made field goals;
- writes the controlled player-week stats and pool scores through the same Supabase persistence path used by the live scorer;
- reads the scores back from Supabase and verifies them;
- verifies Week 1 scoring data is unchanged;
- restores the demo players' prior scoring/stat state before finishing;
- records a scoring_diagnostic data-run result for audit history.

No SQL migration, Supabase setting, or secret change is required.
