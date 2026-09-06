# v0.1.7 — Gate 1 Auth Transition Polish

## Why
A successful Sign In could briefly show a duplicated/ghosted copy of the sign-in form while Streamlit reran to acknowledge the remembered-device browser storage write.

## Fix
- Render the player authentication area inside a dedicated placeholder.
- Clear that placeholder immediately after successful authentication, before the remembered-device bridge acknowledgement rerun.
- Keep the proven v0.1.5+ localStorage + first-party cookie architecture unchanged.
- Preserve one-click sign in/sign out, season-long remembered login, second-device login, and fixed light appearance.

No SQL, Supabase, or secret changes are required.
