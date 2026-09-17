# v1.0.7 Hotfix 7.15 — Focused UI Polish

**Base:** Hotfix 7.14.1 (includes 7.10.1 two-speed live, 7.11 season stats, 7.12 lineup reveal, 7.13 Sunday race, 7.14 personal season story, and 7.14.1 feed protections).

## User-facing changes

1. **Sunday hierarchy:** An abbreviated 1 PM reveal headline and Your Sunday Race appear above full standings. The complete who-picked-whom breakdown and general Sunday storylines are beneath standings in separate, collapsed expanders. Reveal remains unavailable before lock, and emergency backups are private unless activated. The week's public bundle is still read once per 15-second UI refresh; detailed reveal reuses the same computed data.
2. **Picker progress:** A read-only five-position progress strip (`QB / RB / WR / TE / K`) marks the current position and checks only positions already saved by Next. It does not navigate, save or otherwise modify selections.
3. **Mobile tab bar:** Larger, higher-contrast labels, compact owner-control clearance, forced single-row tab layout, preserved 44px+ tap targets. Layout geometry was checked in a Chromium approximation at widths 280, 300, 320, 375, 430 and 1280 px; a real Streamlit Cloud phone/owner-control check remains necessary.
4. **Refresh clarity:** The live screen shows green for an NFL check within 7 minutes, amber for 8–15 minutes, warning for older checks or an absent first refresh. This *only* applies when an actual game is LIVE; no false live-warning banner for finished games or Monday. The timestamp is a last NFL data check, not a promise of play-by-play latency.
5. **Profile polish:** "See X more achievements" matches the hidden count; slightly tighter profile summary card spacing; no obsolete Week 1 notification wording in Add to Home Screen.

## Warm Streamlit deploy safety

UI CSS has its own schema marker/reload guard; app.py refreshes its configuration build key, then reloads Gate 4 before Weekly UI. Weekly UI imports Gate 4 functions by name, so reloading in the reverse order could otherwise retain the previous Sunday view. The new build cache key is `1.0.7-hotfix7.15`.

## Explicitly unchanged

No edits to Supabase schema/SQL, lineup save logic, published pool, eligibility, emergency backup behavior, scoring formula, live backend refresh cadence, AWTRIX, GitHub workflow or provider requests. This package contains UI code, a deploy import guard, release documentation and tests only.

## Verification

318 tests passed, including five additional UI-specific tests. Four historical source-assertion tests were updated to reflect the newly requested page order, narrower nav owner clearance and evergreen wording. All Python modules compiled; `release_guard.py` passed. Chromium layout approximation verified nav touch targets/owner clearance/no horizontal overflow for 280–430 px mobile and 1280 px desktop. Actual live Supabase, Streamlit Cloud mobile UI and physical AWTRIX are **not** exercised locally.

## Install

Extract the ZIP. Open `UPLOAD_TO_GITHUB` and upload **its contents** (including the `tests` folder) into the existing GitHub repository root on `main`; replace matching files. Wait for the Quality Gate to turn green and Streamlit to redeploy. No SQL, workflow replacement, AWTRIX reinstall or secrets change is required.

**Commit:** `v1.0.7 hotfix — polish Sunday UI and lineup picker`

**Tag:** `v1.0.7-hotfix7.15`
