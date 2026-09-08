# Teal's Sunday Pick'em — v1.0.3 Release Notes

**Release:** v1.0.3 — Pick Confirmation + Publish Reliability  
**Baseline:** v1.0.2 Final Full + Signup UX Hotfix  
**Date:** September 8, 2026

## Scope
This release contains only the two changes approved after the real Week 1 pool/pick-flow rehearsal.

### 1. Deliberate lineup selection flow
- Tapping a player now stages the choice **locally and instantly**; Supabase is not written until Next/Return is tapped.
- The selected player now remains on screen with a stronger teal highlight and checkmark.
- Navigation no longer auto-advances after the tap.
- The right-side action becomes **Next: RB →**, **Next: WR →**, **Next: TE →**, **Next: K →**, then **Review My Five →**.
- A newly selected Questionable starter uses **Choose Emergency Backup →** before advancing.
- Emergency-backup selection also remains highlighted until the user deliberately taps Next/Return.
- Existing valid Questionable backups are preserved when simply returning through an edit flow.

### 2. Tuesday pool-publish reliability
- The single Tuesday 12:07 PM ET scheduled publication opportunity is now a retry window at **12:07, 12:17, 12:27, 12:37, 12:47, and 12:57 PM ET**.
- All retries use the existing idempotent `auto` path. Once the pool is published, later retries do not republish or reshuffle it.
- Manual `publish` remains available in GitHub Actions as the emergency fallback.

## Explicitly unchanged
- Player-pool ranking algorithm and top-five choices
- QB/RB/WR/TE scoring
- Kicker scoring: FG = 3, XP = 1, misses = 0, no negatives
- Sunday 1:00 PM ET universal lock
- Emergency-backup activation rules
- Season points, tie handling, co-champions
- PIN/authentication and remembered-device behavior
- Supabase schema and all four SQL migrations
- Live-stat parsing/scoring pipeline
- Monday reconciliation and Weekly Recap logic

## Deployment
No SQL, Supabase, or secret changes are required. The only workflow file changed is `.github/workflows/nfl-refresh.yml`.


### Picker speed hotfix — September 8, 2026
- Player-card taps no longer write to Supabase before confirmation.
- The checkmark/highlight is session-local, so changing your mind between cards creates no database traffic.
- **Next / Return** performs the single position save and then advances.
- If the selected player is Questionable, the starter and emergency backup are staged locally and committed together in one `lineup_picks` upsert.
- Pressing Next on an unchanged already-saved selection skips the redundant upsert entirely.
- The existing lineup snapshot stays warm for up to five minutes while the builder is open to avoid an unnecessary lineup re-read during selection.
- Back discards an unconfirmed local tap.
- No scoring, pool ranking, NFL provider, database schema, auth, lock, or standings behavior changed.
