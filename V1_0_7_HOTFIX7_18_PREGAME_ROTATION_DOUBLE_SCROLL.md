# v1.0.7 Hotfix 7.18 — Pregame Rotation + Double Scroll

This is a clock-only follow-up to Hotfix 7.17.

## Sunday pregame, 10:30 AM–1:00 PM ET
The five-minute slots now repeat a four-way, privacy-safe cycle:

- :00 / :20 / :40 — NFL Sunday Preview
- :05 / :25 / :45 — enabled Commissioner message
- :10 / :30 / :50 — Pick'em Readiness
- :15 / :35 / :55 — current app Season Standings

Because the clock starts at 10:30 AM, its first six pre-lock events are Readiness, Season Standings, NFL Preview, Commissioner, Readiness, Season Standings. The minute-of-hour pattern above remains fixed.

If no Commissioner message is enabled, or season standings are unavailable (for example Week 1), that slot safely falls back to NFL Preview or Readiness. Current-week picks and weekly standings remain private until the 1 PM lock.

## Double scroll
Every activation of these categories now completes two full text passes on AWTRIX:

- NFL Sunday Preview — Saturday and Sunday pregame
- NFL LIVE/current scores — Sunday after lock
- Current Week Pick'em Standings — Sunday after lock

All other ticker categories remain one pass. This uses AWTRIX `repeat: 2`; it does not duplicate feed events, increase provider polling, or queue a second copy.

## Unchanged
- Saturday NFL Sunday Preview still activates every 15 minutes all day ET.
- Sunday post-lock category schedule is unchanged from 7.17.
- Hotfix 7.17 freshness / non-stacking behavior stays intact.
- Caleb Watch remains parked.
- Commissioner melody behavior remains unchanged.
- No scoring formula, lineup, lock, player-pool, auth, NFL provider, or GitHub Actions changes.
