# v0.4.1 — Gate 4 Commissioner Demo/Auth Hotfix

- Keeps the Gate 4 demo inside authenticated Commissioner mode; no player login required.
- Uses a synthetic demo identity and never depends on a real player session.
- Clears stale Gate 4 navigation widget state when entering/exiting demo mode.
- Adds a one-time deployment compatibility guard that reloads weekly_ui only if a stale pre-Gate-4 function signature is resident in the Streamlit process.
- Bumps app version to 0.4.1.
