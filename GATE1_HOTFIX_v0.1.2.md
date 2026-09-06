# v0.1.2 — Gate 1 Cookie Manager Hotfix

## Changes
- Removed `@st.cache_resource` from the `extra_streamlit_components.CookieManager` factory. The cookie manager is a Streamlit component/widget and must not be created inside a cached function.
- Added support for `SUPABASE_SECRET_KEY`, matching the existing Yahtzee deployment naming.
- Kept backward compatibility with `SUPABASE_SERVICE_ROLE_KEY` so the current deployment continues working without a secrets migration.
- No database migration is required. No Yahtzee tables or Pick'em tables are changed.

## GitHub
Commit: `v0.1.2 — Gate 1 Cookie Hotfix`

Commit description: `Fixes Streamlit cached-widget warning for remembered login and aligns Pick'em with the existing Supabase secret-key naming.`

Tag: `v0.1.2`
