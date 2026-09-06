# v0.3.1 — Gate 3 Schedule Resilience Hotfix

- Removes ESPN as a hard dependency for schedule generation and diagnostics.
- Uses nflverse schedules as the primary source; nflverse schedule data updates frequently during the season.
- Keeps ESPN as a replaceable live-status/box-score convenience source.
- ESPN weekly calls now try both documented query shapes (`dates=YYYY` then `season=YYYY`).
- Live refresh falls back cleanly to nflverse if ESPN is temporarily unavailable.
- No database migration or secret change is required.
