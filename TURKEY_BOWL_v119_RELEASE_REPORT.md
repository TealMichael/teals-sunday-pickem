# Teal's Sunday Pick'em v1.0.19 — Turkey Bowl release verification

Prepared from the user-provided full `v1.0.18` source archive on November 18, 2026. This is an **undeployed release package**.

## Scope

- Additional 2026 holiday event for Nov 26, NFL Week 12: CHI@DET, PHI@DAL, KC@BUF only. Wednesday and Friday games cannot enter the event.
- Tuesday Nov 24 12 PM ET publish/open; universal Thursday Nov 26 1 PM ET event lock, additionally enforced by database triggers.
- Five visible Thanksgiving starters per position with a separate 1–5 hidden reserve pool; the pool ranker tolerates only six participating teams and does not change Sunday's ten-candidate contract.
- Isolated Thanksgiving lineups, saved emergencies, validated confirmations, final leaderboard, correction/finalization, separate background refresh, and full extra 12/9/7/6/5/4/3/2/1 season-points scale.
- Equal first-place scores share full points and champion award; archived holiday results are stored by unique event and player (idempotent retry).
- 2026 champions wear 🦃🏆 next to nickname during 2027 season; champion history preserved afterward.
- Sunday game screens, picks, scoring, injury protections, existing ticker/clock schedules, news and account approval are unchanged except additive holiday entry and historical season points.

## Engineering safeguards

- Original Sunday week, lineup and weekly results schemas are not modified. New tables live solely inside `pickem`, RLS enabled, service-role only.
- Existing `pickem.commissioner_remove_account` function is updated to prevent deleting an account with Turkey Bowl history, preserving existing owner protections and session revocation.
- Holiday games are checked against three Thursday matchups; workflow uses separate concurrency group and existing Supabase secrets.
- ESPN summary stat refresh fails closed when neither team's meaningful box score has arrived; no premature zero-point finalization for all players.
- Atomic SQL reserve promotion avoids an intermediate 4-/6-choice pool; special-event write triggers enforce date/lock/ownership/eligibility in database.
- The NFL provider's season-wide schedule is used before the scoreboard fallback; score updates occur in a worker, not on iPhone page taps.

## Executed offline checks

- Source: `v1.0.18` uploaded ZIP. Existing files are preserved except the version/reload and holiday integrations.
- Python compilation: **PASS**.
- `python release_guard.py`: **PASS**.
- Selected unit/contract tests: **35 passed, 3 subtests passed**, no known test failures in this selected set.
- Full `pytest` suite: **NOT RUN** because required `postgrest`, `supabase`, and `streamlit` packages are missing and remote installs are not available here.
- Production SQL migration, GitHub Actions, ESPN live feeds, Streamlit browser and iPhone checks: **NOT RUN**; the installation guide includes mandatory verification.

## Install readiness

**For installation and real-environment validation, not certified production-passed yet.** Run Supabase SQL first, commit the complete browser-upload overlay, then check GitHub Quality Gate and manual smoke tests. Do not claim live Thanksgiving scores until verified on November 26.
