# v1.0.1 — Public Launch Isolation + Mobile Polish

This pre-install hotfix rolls the final real-device findings into v1.0.1:

- Removes the synthetic Gate 2 test week from the public player experience.
- Automatically clears stale public demo-week session state back to the real NFL week.
- Keeps the Gate 2 lineup-builder preview available only in Commissioner → Diagnostics.
- Reserves a mobile navigation safe zone for Streamlit Community Cloud's owner-only lower-right Manage App/avatar control, so Profile remains tappable.
- Replaces the Season-points popover with an inline expander.
- Explicitly forces Streamlit portal/overlay surfaces to the app's light theme so phone dark mode cannot turn help/menu content into a dark unreadable panel.
- Hides the in-app Streamlit developer toolbar where the host allows it.

No SQL, Supabase settings, secrets, or GitHub Actions changes are required.
