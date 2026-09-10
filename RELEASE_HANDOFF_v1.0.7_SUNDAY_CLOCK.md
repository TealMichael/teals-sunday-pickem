# Release Handoff — v1.0.7 Sunday Clock Broadcast + Commissioner Cleanup

Baseline: **v1.0.6 — Automation Hardening**.

## Purpose
Make Sunday Pick'em feel alive in the room through a separate AWTRIX broadcast layer while consolidating accumulated Commissioner diagnostics into one recovery tab.

## Runtime changes
- `clock_broadcast.py` — builds safe, compact app-owned broadcast snapshots.
- `awtrix/PickemSunday.ax` — separate headless AWTRIX client that polls the scoped clock RPC and displays only new events.
- `db/006_sunday_clock.sql` — clock token/settings/snapshot/control tables plus narrow `clock_feed` and `clock_ack` RPCs.
- `store.py` — server-only clock setup/settings/snapshot/token helpers.
- `gate5_ui.py` — new Clock tab; Commissioner cleanup; all diagnostics consolidated under Diagnostics.
- `gate5.py` — best-effort snapshot refresh after Commissioner-owned data changes.
- `scripts/nfl_refresh.py` — best-effort snapshot refresh after normal background NFL updates.
- `automation_recovery.py` — best-effort snapshot refresh after a successful app recovery refresh.
- `app.py` — Gate 5 UI deployment reload guard bumped to schema 4.
- `config.py` — APP_VERSION 1.0.7.
- `release_guard.py` + regression tests/docs.

## Clock data contract
The clock never computes standings or fantasy points. Sunday Pick'em remains source of truth. The server snapshot contains only display-safe derived text: nicknames/ranks/scores after lock, live NFL scores, pool-player spotlights, season standings, and optional Commissioner messages.

Pre-lock `clock_feed` returns only readiness/manual party content. It never exposes picks or post-lock social content.

## Security
- Clock token plaintext is generated server-side and shown only in-session immediately after generation.
- Supabase stores SHA-256 only.
- Clock uses public/publishable key + scoped token; never service-role/secret key.
- Clock tables have RLS enabled and anon/authenticated table access revoked.
- Public client roles may execute only the narrow token-validated clock RPCs.

## Commissioner cleanup
Top-level tools are now:
**Week / Players / Corrections / Clock / Diagnostics**.

Moved into Diagnostics:
- Launch Readiness / Full Week Rehearsal
- Database check
- Automation recovery status
- Recent NFL/Commissioner activity
- Wednesday Live Game Dress Rehearsal
- Gate 2/3/3.5/4 legacy demos and diagnostics

## Protected code
Fresh byte comparison against v1.0.6 confirms no change to:
- `nfl_sync.py`
- `nfl_scoring.py`
- `nfl_sources.py`
- `nfl_rankings.py`
- `live_dress_rehearsal.py`
- `weekly.py`
- `weekly_ui.py`
- `.github/workflows/nfl-refresh.yml`
- `.github/workflows/quality-gate.yml`

## Verification
- pytest: **186/186 PASS**
- Full Week Rehearsal: **9/9 PASS**
- compileall: **PASS**
- release_guard: **PASS**

## Install order
1. Upload the GitHub patch to `main`; wait for Quality Gate green.
2. Run `db/006_sunday_clock.sql` once in Supabase SQL Editor.
3. Open Commissioner → Clock and generate a Clock Token.
4. Download/install `awtrix/PickemSunday.ax` as a separate AWTRIX script.
5. Configure that script with Supabase URL, Supabase publishable/anon key, and scoped Clock Token.
6. Save optional current-week messages.
7. Press Test Clock and confirm the physical panel scrolls the labeled test content.

No hidden GitHub workflow or `.streamlit` file changes are part of this release.
