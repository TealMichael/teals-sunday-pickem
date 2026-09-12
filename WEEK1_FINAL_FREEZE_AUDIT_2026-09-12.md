# Week 1 Final Freeze Audit — Sep 12, 2026

Scope: read-only review of the exact Hotfix 7.1 release candidate, followed only by fixes for concrete Sunday-relevant defects.

## Passed unchanged
- published-pool immutability and hidden saved-starter hydration
- universal 1:00 PM ET DB lock and UI transition
- per-player kickoff injury freeze
- live score preservation on skipped/final/failed provider rows
- flat kicker scoring (3/FG, 1/XP)
- Sunday scheduler cadence / recovery leases / freshness ownership
- pre-lock clock privacy and post-lock ticker cadence
- Hotfix 7.1 rich-fragment AWTRIX rendering path
- auth/PIN protections
- public Live auto-refresh

## Concrete issues found and fixed in Hotfix 7.2
1. The original DB pick trigger predated preserved hidden starters and could reject a backup-clear UPDATE on such a lineup.
2. Injury replacement could select a hidden player whose game had become schedule-ineligible.
3. App/DB save guards did not explicitly reject schedule-ineligible new selections.
4. A Questionable starter could appear backup-ready when its emergency backup's game was no longer eligible.

## Deferred (not Week 1 critical)
Season standings currently use total fantasy points to break equal season-point totals, while the intended end-of-season contract is true co-champions on equal season points. This cannot affect Week 1 and is intentionally deferred to avoid unrelated Saturday code churn.

## Freeze rule
After Hotfix 7.2 passes CI and migration 011 is applied, make no further code changes before Sunday unless a concrete production defect is observed.
