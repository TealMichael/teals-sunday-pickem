# v0.3.6 — Gate 3.5 CDN Box Score Fallback

## Why this patch exists
The legacy ESPN `site.api.espn.com` scoreboard/summary host returned HTTP errors from both Streamlit Cloud and GitHub Actions. That makes it unsuitable as a production hard dependency.

## Changes
- nflverse remains the primary schedule/status source.
- Preseason replay finds the Bears–Titans game in nflverse schedule data and uses its ESPN event id.
- Production player box scores now use ESPN's CDN feed first:
  - `cdn.espn.com/core/nfl/boxscore?xhr=1&gameId=...`
  - then `cdn.espn.com/core/nfl/game?xhr=1&gameId=...`
  - legacy site summary is only a final fallback.
- CDN `gamepackageJSON` responses are unwrapped before the existing player parser runs.
- Live scoring no longer calls the legacy ESPN scoreboard for game status; nflverse handles schedule/status.
- Week 2+ kicker offense ordering no longer depends on ESPN scoreboards.
- nflverse schedule CSV is cached within each worker process so multi-week ranking work downloads it only once.

## Acceptance test
Run the existing GitHub Actions workflow with:
- mode: `preseason_replay`
- week: `0`
- force: off

If it succeeds, Commissioner → Refresh Gate 3.5 Result should show the real box-score replay PASS report.
