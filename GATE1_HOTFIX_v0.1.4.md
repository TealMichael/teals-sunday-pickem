# v0.1.4 — Gate 1 Remembered Login Hotfix

## What changed
- Reads remembered-login cookies through Streamlit 1.63's native `st.context.cookies` on a fresh browser request.
- Uses `extra_streamlit_components.CookieManager` only for cookie writes/deletes.
- Adds a short one-time browser-write settling delay before rerunning after sign-in/account creation.
- Keeps the active opaque session cookie value in Streamlit session state so sign-out can revoke the correct server session.
- Preserves the existing 210-day remembered-device expiration and secure/lax cookie attributes.

## Why
The third-party CookieManager is asynchronous. On a brand-new tab/session its read could race the page render, and an immediate rerun after writing could race the browser cookie write. This caused a valid player to be asked to sign in again after closing and reopening the app.

## No database migration
No SQL changes are required for this hotfix.
