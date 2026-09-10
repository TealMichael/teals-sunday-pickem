# Teal's Sunday Pick'em — Week 1 Launch Checklist

## Before Tuesday noon ET
- Commissioner → Launch → **Run Launch Check**
- No red items
- Automation heartbeat fresh after the next scheduled GitHub Actions run
- Gate 3 scoring diagnostic PASS
- Gate 3.5 real provider replay PASS
- Supabase migration `db/005_automation_hardening.sql` applied
- Commissioner → Week shows **Automation fallback armed**

## Tuesday after noon ET
- Verify the weekly pool auto-publishes shortly after noon
- If GitHub is late, the first active Sunday-tab session after the recovery grace window can safely publish the same validated pool
- Confirm exactly 5 visible choices for QB, RB, WR, TE, K
- Make one real lineup on a phone
- Edit one pick by tapping its review card
- Confirm Questionable backup explanation / selection still works

## Sunday morning
- 8-11 AM ET: backend injury/status refresh is hourly
- Beginning in the 11 AM ET window: GitHub injury/status refresh is every 15 minutes
- If a critical near-lock refresh is overdue, an active Sunday-tab session can recover it after the scheduler grace period
- Commissioner → Week → scan injury warnings and recent provider activity
- Friends make final lineup checks before 1:00 PM ET

## Sunday 1:00 PM ET
- Confirm picks are locked
- Confirm Sunday changes to live standings automatically
- GitHub remains the primary 15-minute live-score worker
- If a live refresh is overdue, an active Sunday-tab session can recover it through the server-only lease
- Tap another player and verify roster/scoring drill-down
- Confirm Storylines render

## Sunday games
- Verify NFL refresh age stays current
- Verify live scores/game status update
- The scheduled worker continues through the late-SNF/overtime buffer
- Commissioner activity may show `App Recovery` only when GitHub was late enough for the fallback to activate
- Manual Commissioner refresh remains the final emergency control

## Monday morning
- Beginning shortly after 9:00 AM ET, GitHub reconciliation retries hourly during the retry window until settled
- If GitHub is delayed, an active Sunday-tab session can recover final reconciliation after the grace period
- Confirm reconciliation produces FINAL
- Confirm weekly champion/co-champions
- Confirm season points
- Confirm History row
- Confirm Trophy/Profile totals
- Confirm champion football celebration

## Optional Sunday Clock — v1.0.7
- Run `db/006_sunday_clock.sql` once.
- Generate the scoped token under Commissioner → Clock.
- Install `PickemSunday.ax` separately on AWTRIX; do not replace school clock scripts.
- Press Test Clock before Sunday.
- Confirm pre-lock test/normal output does not expose anyone's picks.
- Clock setup is optional and must never block the player app or live scoring.
