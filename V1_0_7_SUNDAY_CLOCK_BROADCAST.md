# v1.0.7 — Sunday Clock Broadcast + Commissioner Cleanup

## What changed
v1.0.7 adds a separate Sunday-only AWTRIX broadcast layer and cleans up Commissioner navigation without changing the player game or the proven live-scoring engine.

### Commissioner → Clock
- Three optional, week-specific message boxes:
  - Welcome / Who's Here
  - Food or Party Message
  - Custom Message
- Blank/disabled boxes never carry stale content into the next NFL week.
- Automatic Sunday content continues even if the Commissioner does nothing.
- Full current-week standings include every registered player.
- All currently LIVE Sunday NFL games can scroll on the clock.
- Player Update uses only visible players from that week's 25-player Pick'em pool and only while their game is LIVE.
- Starting Week 2, the full app-owned season standings join the rotation.
- Pick'em Pulse may feature Most Popular, Going Solo, or Same Brain after lock. Closest Race is intentionally not used.
- Test Clock arms a short synthetic test sequence without touching real scores, lineups, standings, or NFL data.

### Privacy / security
- Before the universal Sunday 1:00 PM ET lock, the clock feed never reveals picks, ownership, player-selection storylines, or standings.
- AWTRIX receives only one already-safe display string at a time.
- The physical clock uses a Supabase publishable/anon key plus a separate scoped, revocable clock token.
- The scoped token is stored in Supabase only as a SHA-256 hash. The plaintext token is shown only immediately after generation in the Commissioner session.
- The Supabase service-role/secret key is never sent to the clock.
- The Pick'em AWTRIX script is separate from the existing Class Schedule and Fact Challenge scripts.

### Sunday rhythm
The server exposes at most one new clock event per five-minute slot. Typical post-lock rotation:
- :00 — weekly standings
- :05 — live NFL scores
- :10 — Pick'em-pool Player Update
- :15 — weekly standings
- :20 — season standings (Week 2+) or Pick'em Pulse (Week 1)
- :25 — optional Commissioner message
- :30 — weekly standings
- :35 — live NFL scores
- :40 — Pick'em-pool Player Update
- :45 — weekly standings
- :50 — season standings (Week 2+) or Pick'em Pulse
- :55 — optional Commissioner message

Missing categories fall back to automatic Pick'em content rather than leaving the clock blank.

### Sunday-only behavior
- Normal broadcast begins about 10:30 AM ET Sunday.
- It stops at midnight after the Sunday slate.
- Monday–Wednesday the headless script backs off to a very low polling rate so school-day clock use remains effectively untouched.
- Thursday–Saturday it checks once per minute so Test Clock can be used during setup.

## Commissioner cleanup
The main Commissioner navigation is now:

**Week • Players • Corrections • Clock • Diagnostics**

The old Launch tab is gone. Launch readiness/full-week rehearsal, database checks, run history, live-game rehearsal, and legacy Gate demos are all consolidated under **Diagnostics** and collapsed by default.

## Protected systems
No changes were made to:
- `nfl_sync.py`
- `nfl_scoring.py`
- `nfl_sources.py`
- `nfl_rankings.py`
- `live_dress_rehearsal.py`
- `weekly.py` / `weekly_ui.py`
- `.github/workflows/nfl-refresh.yml`
- `.github/workflows/quality-gate.yml`

The clock snapshot is best-effort only: if the optional clock schema is missing or unavailable, normal player/Commissioner/NFL workflows continue.

## One-time install
1. Deploy the v1.0.7 GitHub patch and wait for Quality Gate to pass.
2. Run `db/006_sunday_clock.sql` once in Supabase SQL Editor.
3. Open Commissioner → Clock.
4. Generate a scoped Clock Token and copy it immediately.
5. Install `awtrix/PickemSunday.ax` as a separate AWTRIX headless script.
6. In its settings enter the Supabase URL, Supabase publishable/anon key, and scoped Clock Token.
7. Press **Test Clock** in Commissioner mode.

Do not replace or edit the existing Class Schedule or Fact Challenge AWTRIX scripts.
