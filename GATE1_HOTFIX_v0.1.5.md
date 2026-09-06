# v0.1.5 — Gate 1 Proven Remembered-Login Rebuild

## Why this exists
Gate 1 v0.1.4 still returned a remembered player to the sign-in screen after closing and reopening the browser tab.

The failure was architectural: Pick'em was still using `extra-streamlit-components` CookieManager, while the currently working Yahtzee app uses a first-party Streamlit Components v2 bridge that persists the high-entropy device token in browser `localStorage` and synchronizes a first-party cookie.

## Fix
- Removed `extra-streamlit-components` completely.
- Added a hidden Streamlit Components v2 localStorage bridge.
- Synchronizes the same opaque revocable token to a first-party `Secure; SameSite=Lax` cookie.
- Uses `st.context.cookies` for the fresh-request fast restore path.
- Uses localStorage as the fallback when the cookie is unavailable or stale.
- Does not mark restore complete until the async Components v2 read is ready.
- Keeps transient Supabase failures from deleting a valid browser token.
- Sign-out revokes the server session and clears both cookie and localStorage.

## GitHub
Commit message:
`v0.1.5 — Gate 1 Remembered Login Rebuild`

Commit description:
`Replaces the unreliable CookieManager flow with the proven first-party localStorage + cookie remembered-login architecture used by Yahtzee.`

Tag:
`v0.1.5`

## Install
Replace:
- `app.py`
- `config.py`
- `requirements.txt`

No SQL migration and no Streamlit secret changes are required.
