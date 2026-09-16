# v1.0.7 Hotfix 7.13 — Your Sunday Race

A compact, read-only personalized race card on the Sunday screen, immediately after the existing 1 PM Lineup Reveal and before general Sunday Storylines. This is a cumulative browser-upload patch that also includes the 7.12 lineup-reveal helper for anyone still running 7.11.

- Shows the signed-in participant's exact current competition rank, score, score gaps to the next distinct-score competitor above and below, and any tied friends.
- Shows a participant's top **currently scoring** player and a strictly labeled latest-NFL-update summary of their active players' game statuses. When one distinct nearest rival has games still live or scheduled, shows that rival's game statuses too.
- Does not invent ranking movements, touchdowns, win odds, projections, remaining-point estimates, or unseen NFL events. Missing game data is labeled unavailable, never treated as FINAL.
- Locked Sunday / provisional Sunday only: no personalization or lineup reveal before 1 PM ET, in demo mode, or on the final Monday recap.
- Relies on the *existing* `get_week_public_bundle` and `build_weekly_leaderboard` results. No extra NFL requests, database queries, new tables, writes, notifications, or separate refresh loops.
- Already-activated emergency substitutes follow the existing scorer; unactivated backup identities and IDs never enter the rendered card. Player names are HTML escaped.
- The current five-minute GitHub backup, two-speed active Sunday engine, 15-second app reads, 15-second AWTRIX reads, lineup immutability, score calculations, and Tuesday newsletter are untouched.

**Deployment:** Upload the *contents* of `UPLOAD_TO_GITHUB` to the repository root on `main`. Works as the next cumulative patch over either already-installed 7.12 or 7.11 (the 7.12 reveal files are bundled again). No Supabase SQL, no AWTRIX reinstall, and no workflow-file change.

**Commit:** `v1.0.7 hotfix — add personalized Sunday race`

**Tag:** `v1.0.7-hotfix7.13`

**Validation:** 295 local tests passed; Python compilation and release guard passed. Real NFL/live production content has not been tested against the deployed Supabase and should be visually checked after Sunday lock.
