-- Read-only Turkey Bowl installation verification. Run after migration 018.
-- Expected: one event for season 2026 with the correct lock; six RLS-enabled
-- tables; zero pool/game/lineup/result rows before the worker publishes them.
SELECT event_type, season, nfl_week, game_date,
       opens_at AT TIME ZONE 'America/New_York' AS opens_et,
       locks_at AT TIME ZONE 'America/New_York' AS locks_et,
       published_at, finalized_at
FROM pickem.special_events WHERE event_type='turkey_bowl' AND season=2026;

SELECT tablename, rowsecurity
FROM pg_tables
WHERE schemaname='pickem'
  AND tablename IN ('special_events', 'special_games', 'special_pool',
                    'special_lineups', 'special_picks', 'special_results')
ORDER BY tablename;

SELECT p.position, COUNT(*) AS choices, COUNT(*) FILTER (WHERE is_visible) AS visible
FROM pickem.special_pool AS p
JOIN pickem.special_events AS e ON e.id=p.event_id
WHERE e.season=2026 AND e.event_type='turkey_bowl'
GROUP BY p.position ORDER BY p.position;

SELECT (SELECT COUNT(*) FROM pickem.special_games g JOIN pickem.special_events e ON e.id=g.event_id WHERE e.season=2026) AS holiday_games,
       (SELECT COUNT(*) FROM pickem.special_lineups l JOIN pickem.special_events e ON e.id=l.event_id WHERE e.season=2026) AS holiday_lineups,
       (SELECT COUNT(*) FROM pickem.special_results r JOIN pickem.special_events e ON e.id=r.event_id WHERE e.season=2026) AS holiday_results;
