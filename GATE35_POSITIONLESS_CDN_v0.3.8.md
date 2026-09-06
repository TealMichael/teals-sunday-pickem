# v0.3.8 — Gate 3.5 Positionless CDN Replay Fix

The real ESPN CDN box score successfully reached the parser, but CDN athlete rows did not include position metadata. Production Pick'em scoring already does not depend on ESPN position: it matches real stats by team + player name and scores them using the position stored in the weekly player pool.

This patch makes the real preseason replay use the same contract. It targets five independently verified real players from Bears–Titans (Tyson Bagent, Roschon Johnson, Zavion Thomas, Kylen Granson, Joey Slye), validates real stat anchors across all five Pick'em positions, applies the known Pick'em position locally, round-trips through Supabase, verifies Week 1 isolation, and cleans up.
