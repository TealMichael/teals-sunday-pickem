# Release Handoff — v1.0.4 Public UX Polish

## Baseline
Built from `Teals_Sunday_Pickem_v1.0.3_Final_Full_LIVE_CACHE_PAGINATION.zip`, which contains the latest v1.0.3 picker performance work and Commissioner live-game diagnostics used in the successful Wednesday full-game rehearsal.

## Scope
This release intentionally changes only player-facing UX and version/reload metadata:
- `weekly_ui.py` — richer first-time How to Play + SAVE MY LINEUP moved above secondary Change controls;
- `gate4_ui.py` — permanent profile rules renamed **How to Play & Scoring**;
- `config.py` — version bump to 1.0.4;
- `app.py` — weekly UI hot-deploy schema guard bump;
- release docs / version-contract tests / new v1.0.4 UX regression test.

## Protected behavior
Do not drift scoring, live NFL ingestion, pool ranking, auth, database schema, lock rules, emergency-backup rules, Select → highlight → Next, standings, recap, or Commissioner diagnostics.

## Deployment
No SQL, Supabase settings, secrets, or hidden files need updating. No GitHub Actions workflow is changed by this release.
