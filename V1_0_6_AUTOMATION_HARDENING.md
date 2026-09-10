# v1.0.6 — Automation Hardening

GitHub Actions remains the primary NFL refresh scheduler. v1.0.6 adds a guarded Streamlit-server fallback for the moments where exact timing matters and GitHub scheduled jobs are delayed.

## What changed
- Tuesday pool publication can recover from the public Sunday tab if it is still unpublished 10 minutes after opening.
- During the final two hours before Sunday lock, stale injury/status data can recover after the 15-minute schedule plus a 2-minute grace period.
- From Sunday 1 PM ET through the overnight live window, stale live scoring can recover after the same 17-minute threshold.
- Monday final reconciliation can recover after the normal 9 AM window plus a short grace period.
- A server-only Supabase refresh lease prevents multiple active app sessions from duplicating the same provider refresh.
- Commissioner Week view reports whether the fallback lease is installed and shows the latest app-recovery event.

## Safety
- Normal page loads do not poll providers.
- Recovery only runs in launch-critical windows and only when the corresponding backend run is stale.
- Failed recovery attempts are throttled.
- Any fallback error is non-fatal to the player app; GitHub/manual Commissioner controls remain available.
- Scoring formulas, player matching, lineup persistence, pool ranking, and the validated live-data parser were not changed.

## Required one-time database step
Run `db/005_automation_hardening.sql` once in the Supabase SQL Editor. Until that is applied, GitHub scheduling continues normally and the app simply declines to run the fallback.
