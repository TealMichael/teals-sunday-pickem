# v1.0.7 Hotfix 7.14 — Achievements + My Season Story

One read-only Profile improvement combining meaningful earned achievements with each participant's season-to-date progression. Built on the full installed Hotfix 7.13 baseline, including the 7.12 Lineup Reveal, 7.13 Your Sunday Race, 7.11 Season Stats, and 7.10.1 two-speed live engine.

## On the Profile tab

- **My Season Story**: current season rank and points, weeks played, personal-best weekly score, and an individual weekly timeline (weekly finish, fantasy score, season points earned, cumulative season points, season rank and rank movement). Latest three weeks appear immediately; older weeks live under a compact expander.
- **My Achievements**: a small earned-only set: Opening Kickoff, Podium Debut, First Victory (including co-wins), 100-Point Club, Podium Hat Trick (three genuinely consecutive top-three weekly finishes), Big Climb (at least three positions gained in season standings), and Season Leader. Each badge includes the first week it was actually earned. Up to four show before the optional expander.
- All achievements and rank changes come from `pickem.weekly_results` archived after Monday FINAL reconciliation, using existing season tie-break rules. No tentative Sunday results or invented rankings, missed-week zero finishes, simulated stats, or unverified Perfect Five claims.
- One existing archive query is reused for personal totals, the timeline, and badges; no extra external API calls and no new Supabase table. The helper is purely functional and performs no writes.

## Safety and scope

- Profile presentation only. No changes to publishing, weekly pool, picker order, saved starters/backups, Sunday lock, fantasy scoring, injury handling, 2-/3-minute live refresh, AWTRIX, or the Tuesday newsletter.
- The *Perfect Five* badge is deliberately deferred: the app does not retain historic individual starter lists after the following Tuesday, so awarding it across the season would require an explicit verified archival mechanism. Never infer this badge from scores alone.
- Historical snapshot nicknames are not used to select the participant; permanent `player_id` is the key. Only the signed-in participant's season story is displayed. Names do not enter the new HTML rendering, and all displayed text is escaped.
- New UI build schema is `GATE4_UI_SCHEMA_VERSION = 9`, with matching warm-deploy guard in `app.py`, and `APP_BUILD_VERSION = "1.0.7-hotfix7.14"`. Public app version stays 1.0.7.

## Installation

Extract the ZIP. Upload the *contents* of its visible `UPLOAD_TO_GITHUB` folder into the GitHub repository root on `main`. Replace matching root files and keep `tests/` nested. Do not upload `README_FIRST.txt` or the `UPLOAD_TO_GITHUB` folder itself. This package includes the unchanged 7.12/7.13 helpers for cumulative compatibility; **do not separately reinstall earlier ZIPs**.

No Supabase SQL, AWTRIX reinstall, or GitHub workflow change.

**Commit:** `v1.0.7 hotfix — add personal achievements and season story`

**Tag:** `v1.0.7-hotfix7.14`

**Validation:** 306 local tests passed, all modified Python modules compile, release guard passed. Real Profile UI and Week 1 achievements need a quick visual check against the deployed account after Streamlit redeploys; no live Supabase access was available during this local test.
