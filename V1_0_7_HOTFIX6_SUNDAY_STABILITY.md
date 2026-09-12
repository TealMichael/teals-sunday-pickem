# Teal's Sunday Pick'em v1.0.7-hotfix6 — Sunday Stability Audit

This release is a Sunday reliability hardening pass. It is intentionally focused on failure modes that could make the first live Sunday feel broken.

## Production fixes

1. Live-score preservation
- A FINAL game already captured will not be recalculated from an empty feed and zeroed later.
- One failing ESPN game no longer blocks scoring for every other live game.
- Missing player rows preserve the last valid score instead of silently becoming 0.
- A total live-provider failure leaves prior scores untouched.

2. Live Sunday auto-refresh
- The public Live Sunday view rereads Supabase every 60 seconds.
- An open phone no longer needs a manual browser refresh to see updated standings.
- NFL provider polling remains backend-owned; phones do not hammer ESPN.

3. 1:00 PM lock transition
- Open pre-lock screens check the lock transition every 15 seconds.
- The database lock remains authoritative.
- Phones left open around 1:00 automatically move into the locked/live experience.

4. Emergency-backup correctness
- Injury status freezes for each pool player at that player's kickoff.
- An in-game injury cannot retroactively activate an emergency backup.
- An emergency backup must itself remain eligible and not OUT.

5. Freshness ownership
- Post-lock injury-only refreshes do not overwrite the shared live-score freshness timestamp.
- This prevents stale live scoring from looking healthy and suppressing recovery.

6. Scheduler cadence
- The :07/:22/:37/:52 worker cadence uses run start time rather than completion time.
- Normal GitHub startup jitter is tolerated, preventing accidental every-other-run skipping.

7. Automation recovery
- The first post-lock browser does not immediately run an expensive live-score rescue at exactly 1:00.
- GitHub gets its normal 1:07 run window first.
- Recovery leases are longer to reduce duplicate provider work across households.

8. Live game-state quality
- ESPN summary data can update real period, clock, score, and FINAL state over slower schedule heuristics.
- Schedule-ineligible starters clearly require replacement.

9. Monday finalization safety
- A missing final nflverse player row does not overwrite a valid captured ESPN score with 0.

10. Provider efficiency
- The large Sleeper player payload is downloaded once per injury refresh cycle, not once per position.

11. Warm-deploy protection
- Internal build generation is now `1.0.7-hotfix6` while public version remains `1.0.7`.
- Sunday-critical modules have deploy-generation guards so a warm Streamlit worker does not keep old classes/functions after a multi-file hotfix.

## Deliberately unchanged
- 1:00 PM ET database lock
- Pick scoring and kicker rules
- Published-pool / saved-lineup protection from Hotfix 3
- Compact picker and injury-status UI from Hotfix 4
- 15-minute NFL clock-score cadence from Hotfix 5
- Authentication / PIN behavior
- Working AWTRIX RPC/token architecture

## Database / AWTRIX
No new Supabase SQL migration is required for Hotfix 6.
No AWTRIX script change is required.
No hidden-file change is required.

## Validation
- 217 / 217 pytest tests passed
- Python compile passed
- release_guard: PASS
