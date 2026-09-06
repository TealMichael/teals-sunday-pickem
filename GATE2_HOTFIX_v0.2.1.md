# v0.2.1 — Gate 2 Runtime Cache + Onboarding Hotfix

## Fixes
- Prevents Streamlit from reusing a cached `SupabaseStore` instance created from the prior Gate 1 class after a deploy. The app version is now part of the `st.cache_resource` key.
- Replaces fragile custom onboarding HTML with native bordered Streamlit cards so the 1 / 2 / 3 steps render cleanly on desktop and mobile.

## Why the AttributeError occurred
The GitHub `store.py` already contained `complete_onboarding`, but the running Streamlit process could retain the cached Gate 1 `SupabaseStore` object across the incremental deploy. That old in-memory class did not have the Gate 2 method.

## Install
Replace `app.py`, `config.py`, and `weekly_ui.py`. No SQL, Supabase, or secret changes are required.
