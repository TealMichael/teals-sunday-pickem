# v0.3.7 — Gate 3.5 Direct Replay Event

## Why this hotfix exists
The production replay reached GitHub Actions successfully, but the diagnostic stopped before the ESPN CDN call because nflverse's schedule release did not return the selected 2026 preseason Bears–Titans matchup.

That schedule lookup is unnecessary for a one-game acceptance test. The replay is intended to validate the real box-score transport/parser and scoring pipeline, not preseason schedule discovery.

## Change
- The production Gate 3.5 replay now uses the known completed ESPN event id `401874394` for Chicago 24 at Tennessee 15.
- The optional injected schedule-provider path remains available for unit tests and extra diagnostics.
- Production regular-season schedule logic is unchanged and still uses nflverse.
- Week 1 remains isolated and the replay cleanup behavior is unchanged.

## Install
Replace:
- `preseason_replay.py`
- `config.py`

No SQL, Supabase, Streamlit secret, or GitHub Actions workflow changes are required.
