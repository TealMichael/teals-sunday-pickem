# v0.4.3 — Gate 4 Native App-Shell Polish

A focused mobile-first UI pass after Gate 4 functional acceptance.

## Navigation
- Keeps exactly four persistent top-level destinations: Sunday, Leaderboard, History, Profile.
- Replaces platform-dependent emoji navigation with consistent Material icons.
- Uses icon-above-label tab-bar layout so "Leaderboard" no longer truncates.
- Adds a compact floating bottom surface with safe-area spacing for iPhones.
- Keeps a clear teal selected state while avoiding a large selected button block.
- Preserves navigation state across Streamlit reruns.

## Density / hierarchy
- Tightens Gate 4 section headings and vertical rhythm.
- Reduces oversized whitespace in storylines, weekly standings, season rows, history, and profile stats.
- Keeps touch targets large while making rows visually more compact.
- Slightly reduces the repeated brand hero footprint without changing branding.

## Scope
No scoring, NFL provider, Supabase, auth, lineup, season-points, or Commissioner logic changes.
