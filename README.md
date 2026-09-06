# Teal's Sunday Pick'em — v0.1.1 Gate 1

Gate 1 is the secure foundation for the friends-only Sunday fantasy pick'em app. This revision is specifically configured to share the existing **Yahtzee Supabase project** while keeping all Pick'em data inside its own `pickem` schema.

## Included now
- New-player signup: unique nickname, one emoji, 4-digit PIN.
- Case-insensitive nickname uniqueness.
- Slow salted + server-peppered PIN hashing. Plain PINs are never stored in Supabase.
- Season-long remembered-device login using an opaque random token. The cookie does not contain the PIN.
- Multiple remembered devices per player.
- Login throttling for the low-entropy 4-digit PIN model.
- Separate Commissioner authentication using a username + 6-digit PIN stored only in Streamlit secrets.
- Server-only Supabase data access with RLS enabled and no anon/authenticated table access.
- All Pick'em tables live in the isolated `pickem` schema; existing Yahtzee tables in `public` are not modified.
- Mobile-first clean shell ready for Gate 2.

## Intentionally NOT in Gate 1
Weekly player pool, picks, NFL schedules/stats, leaderboards, commissioner PIN reset, demo week, and scoring. Those are added gate-by-gate so this checkpoint stays testable and rollback-safe.

## Supabase requirement
Because `supabase-py` uses the Data API, add `pickem` to the Yahtzee project's **Data API → Exposed schemas** list. The SQL migration grants access only to `service_role`; `anon` and `authenticated` remain revoked.

## Run locally
1. Open the existing Yahtzee Supabase project.
2. Run `db/001_gate1_foundation.sql` in its SQL Editor.
3. In Supabase Project Settings → Data API, add `pickem` to **Exposed schemas** without removing `public`.
4. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and fill it locally. Never commit that file.
5. Install dependencies: `pip install -r requirements.txt`
6. Run tests: `pytest -q`
7. Run guard: `python release_guard.py`
8. Launch: `streamlit run app.py`

## Deployment
Use a separate GitHub repo + separate Streamlit Community Cloud app. Reuse the Yahtzee Supabase URL/service-role key only in Streamlit Secrets; do not copy them into GitHub.
