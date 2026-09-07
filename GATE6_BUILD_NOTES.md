# v0.6.0 — Gate 6 Launch Readiness

Gate 6 is the final pre-release hardening pass. It deliberately avoids new game mechanics and instead makes the already-green Gates safer, faster, easier to monitor, and easier to recover if a provider or UI layer has a bad moment.

## Commissioner → Launch
A new **Launch** destination provides two production-safe checks:

### Run Launch Check
Phase-aware go/no-go audit covering:
- Supabase connectivity
- Tuesday-open / Sunday-1:00-PM-ET timing contract
- stored eligible Sunday schedule
- weekly player-pool state (including reserve rankings after publication)
- previously proven Gate 3 scoring diagnostic
- previously proven Gate 3.5 real-box-score replay
- GitHub Actions automation heartbeat
- recent current-week provider failures
- PIN hashing / login-throttling baseline
- registered-player readiness

The audit is read-only. It never publishes a pool, edits a lineup, or changes a score.

### Run Full Week Rehearsal
A deterministic in-memory rehearsal verifies:
- pre-open → open → locked phase changes
- exact Sunday 1:00 PM ET lock
- fractional scoring
- emergency-backup activation
- incomplete-lineup zero scoring
- weekly tie handling
- traditional competition ranking
- season co-champion tie behavior

No Supabase or provider data is changed.

## Reliability hardening
- Player and Commissioner render paths now have a privacy-safe error boundary. Friends see a friendly retry message instead of a Streamlit/Python traceback.
- Runtime incidents record only scope, exception type, and app build; raw exception strings are not persisted.
- Live Sunday displays a human-readable NFL refresh age and warns when live data is more than 45 minutes stale.
- Future weeks use their actual week label instead of hard-coded “Week 1 opens Tuesday.”
- GitHub NFL automation now writes an `auto_cycle` heartbeat on every scheduled run so Commissioner mode can detect a silent scheduler outage.
- Worker coverage extends through 1:30 AM ET for unusually long Sunday Night Football/overtime.
- NFL refresh jobs use one concurrency group so manual and scheduled refreshes cannot overlap.

## Performance
- Weekly-results reads are cached for 30 seconds and invalidated immediately when results are rewritten.
- Season-champion reads are cached for 60 seconds and invalidated immediately on updates.
- Existing Gate 2 lineup snapshots and Gate 4 public-bundle cache remain intact.

## Continuous quality gate
Adds `.github/workflows/quality-gate.yml` so every push / pull request automatically runs:
- pytest
- Python compile check
- release_guard

No production secrets are needed for this CI workflow.

## Player polish
- Profile now includes optional **Add to Home Screen** directions for iPhone/iPad and Android.
- Web Push is intentionally deferred until after Week 1. The core app does not depend on notification permissions or a service worker to launch successfully.

## Database / secrets
No SQL migration. No new Streamlit secrets. No new GitHub repository secrets.
