# Hotfix 7.15.2 — mobile nav dock tightened above Streamlit host chrome

**Cause:** Hotfix 7.15.1 successfully moved the four-tab mobile navigation above Streamlit Cloud's floating owner avatar/logo so the *Profile* tab could be tapped again on iPhone. The remaining issue was purely visual: the nav sat higher than necessary, leaving an awkward empty gap above the host chrome.

**Change:** On viewport widths up to 480 CSS px, lower the floating four-tab nav from `5.5rem + safe-area-inset-bottom` to `4.1rem + safe-area-inset-bottom` so it rests snugly above the Streamlit avatar/logo area while still preserving clean tap clearance. Bump `UI_THEME_SCHEMA_VERSION` to `4` and `APP_BUILD_VERSION` to `1.0.7-hotfix7.15.2` so the new CSS reliably wins in a warm Streamlit Cloud worker.

**Scope:** `ui.py`, `app.py`, `config.py`, and one focused nav regression test only. No changes to lineup persistence, signup/auth, live scoring, Sunday automation, AWTRIX, injuries, or season-story logic. No SQL.

**Validation:** Static regression checks for mobile nav docking and warm-worker cache busting updated and passing locally. This is a presentation-only adjustment on top of the working 7.15.1 Profile-tab fix.

**Commit:** `v1.0.7 hotfix — tighten mobile bottom nav above Streamlit chrome`

**Tag:** `v1.0.7-hotfix7.15.2`
