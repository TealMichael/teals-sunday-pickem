# v1.0.7 Hotfix 7.17 — Clock Responsiveness + Saturday NFL Preview

## Why this release exists

During live Sunday use, the Streamlit app could show current fantasy points while the AWTRIX NFL score ticker lagged substantially behind. The clock snapshot and NFL scoreboard travel through a separate path from fantasy scoring. A recent Pick'em-player game update could make the active live lane treat the *whole* NFL slate as fresh even when unrelated games were stale, and AWTRIX's normal notification queue could make a newer sports item wait behind an older one.

This release fixes those clock-specific freshness paths without changing scoring formulas, lineups, player pools, lock behavior, authentication, or the Sunday fantasy-stat cadence.

## Changes

### 1. Full NFL scoreboard freshness is independent

- The active Sunday lane now decides whether the lightweight ESPN scoreboard refresh is due from the last successful **full-scoreboard** run, not the freshest individual game row.
- A fresh Pick'em game can no longer mask stale scores elsewhere in the league.
- With an active app session, the lightweight full-scoreboard lane remains approximately every 2 minutes.
- The five-minute shared GitHub live worker now attempts the full ESPN scoreboard before the pool-player scoring pass, giving the clock a current whole-slate fallback even when nobody has the app open.
- If that lightweight scoreboard request fails, the existing scoring path falls back to the durable schedule/live state instead of failing fantasy scoring.

### 2. AWTRIX sports messages stop waiting behind stale sports messages

- Fast-changing automatic categories (`live_games`, weekly standings, player updates, season standings, pulse, readiness, Saturday preview) use `stack:false` behavior on the device.
- Commissioner/manual messages keep normal stacking behavior, including optional melodies.
- Sunday polling is tightened to 10 seconds so a new five-minute/quarter-hour feed slot is picked up quickly.
- Saturday polling is 30 seconds; the feed itself emits only one event per 15-minute preview slot, so no duplicates are created.

AWTRIX documents `stack:false` as replacing the notification currently on screen instead of adding the new notification behind it. This is used only for fast-changing automatic content.

### 3. Caleb Watch is parked, not deleted

- The clock no longer emits Caleb Watch slots.
- :10 and :40 are normal Pick'em-pool Player Updates.
- The Python Caleb Watch builder remains in source so the feature can be restored later without rebuilding it from scratch.
- The scheduled worker no longer refreshes the parked Caleb special data.

### 4. Saturday NFL Sunday Preview

For the entire local Saturday before a real NFL Sunday:

- the clock feed is active all day;
- an **NFL SUNDAY PREVIEW** appears every 15 minutes;
- it shows the Sunday matchups and kickoff times from the week's schedule;
- it is schedule-only and does not expose Pick'em selections, lineup ownership, fantasy points, or standings before lock.

The existing Saturday backend refresh schedule remains unchanged. A Friday/Saturday clock snapshot is enough to populate the preview, and Commissioner → Clock → Refresh Clock Preview can populate it immediately after deployment.

### 5. Existing Sunday protections retained

The 7.14.1 game-state rollback guards are carried forward in `nfl_sync.py`: a lagging provider cannot move FINAL back to LIVE/SCHEDULED or LIVE back to SCHEDULED. No `store.py` or lineup mutation code is changed by this release.

## Sunday post-lock ticker cadence

- :00 — weekly standings
- :05 — NFL LIVE scores
- :10 — Player Update
- :15 — weekly standings
- :20 — NFL LIVE scores
- :25 — season standings / pulse
- :30 — weekly standings
- :35 — NFL LIVE scores
- :40 — Player Update
- :45 — weekly standings
- :50 — NFL LIVE scores
- :55 — Commissioner message

## Validation

A reconstructed cumulative app (through Hotfix 7.16 plus this patch) completed:

- `327 passed` in the full local pytest suite
- `release_guard.py: PASS`
- full Python `compileall`: PASS
- focused Hotfix 7.17 regression checks for whole-scoreboard freshness, scoreboard fallback, Saturday preview privacy, Caleb parking, AWTRIX replacement behavior, and warm-deploy version guards

External provider timing, GitHub scheduling, Supabase production state, and the physical AWTRIX device still require the normal post-deploy live check.

## Installation

1. Run `RUN_FIRST_IN_SUPABASE.sql` once in the football Supabase SQL Editor. It is safe to rerun.
2. Upload the **contents** of `UPLOAD_TO_GITHUB` to the repository root, preserving `awtrix/`, `db/`, `scripts/`, and `tests/`.
3. Replace only the physical clock's `PickemSunday.ax` with the included version. Keep the existing Supabase URL, publishable key, and clock token.
4. Open Commissioner → Clock and press **Refresh Clock Preview** once.
5. Press **Test Clock**. The synthetic sequence now includes an NFL Sunday Preview sample and no Caleb Watch sample.

No token rotation is required. Do not reinstall the classroom clock scripts. The optional Commissioner melody migration/settings remain compatible.

**Commit:** `v1.0.7 hotfix — fresher NFL clock scores and Saturday previews`

**Tag:** `v1.0.7-hotfix7.17`
