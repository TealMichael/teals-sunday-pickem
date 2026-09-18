# Hotfix 7.15.1 — iPhone Profile tab / Streamlit owner avatar overlap

**Cause:** In Hotfix 7.15 the floating four-tab navbar was docked near the bottom edge and attempted to reserve only a narrow right-hand zone for the Cloud owner avatar. On the owner's iPhone, the Cloud avatar still sat over the *Profile* tab and intercepted taps. This is a navigation hit-target problem, not a login or Profile-data problem.

**Change:** On viewport widths up to 480 CSS px, position the entire four-tab bar `5.5rem + safe-area-inset-bottom` above the screen bottom, restore symmetric padding and full four-tab widths, remove the decorative football occupying the former right-hand safe zone, and increase content's bottom padding to `12.75rem` so the last card remains reachable while scrolling. Bump `UI_THEME_SCHEMA_VERSION` to 3 and `APP_BUILD_VERSION` to `1.0.7-hotfix7.15.1` to refresh CSS in a warm Streamlit process.

**Scope:** `ui.py`, `app.py`, `config.py`, and navigation regression tests only. No modifications to `gate4_ui.py`, lineup/roster persistence, scoring, injury updates, the two-speed refresh engine, AWTRIX, or workflow files. No SQL.

**Validation:** Reconstructed Hotfix 7.15 plus this patch: 306 automated tests passed, `py_compile` passed, release guard passed. Live Streamlit Cloud/iPhone tap still needs visual confirmation after deployment.

**Commit:** `v1.0.7 hotfix — unblock mobile Profile tab under Streamlit owner avatar`

**Tag:** `v1.0.7-hotfix7.15.1`
