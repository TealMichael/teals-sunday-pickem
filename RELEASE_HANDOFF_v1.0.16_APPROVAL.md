# v1.0.16 release handoff — restricted family player access

Baseline: user-provided complete v1.0.15 source package. No changes were made directly to the production database or GitHub account.

## Behavior
- New registrations write `pickem.players.account_status='pending'` and receive no session/cookie.
- Existing players are grandfathered `approved` by the SQL migration.
- Login with correct PIN is allowed only if approved; pending accounts get an approval message and disabled users are denied.
- Remembered session restore checks account status. In-memory Streamlit logins also recheck status on each app rerun, to revoke already-open tabs.
- Public player lists and rankings' zero-point player roster exclude pending/disabled accounts.
- Commissioner approval/rejection and safe removal are integrated into the existing Players tool.
- SQL RPC `pickem.commissioner_remove_account(uuid)` runs account deletion/disabling atomically. It preserves accounts with lineups, weekly results, season champion archives, or social reactions. All sessions are invalidated by delete cascade or explicit revocation.
- Existing commissioner identity protection is enforced at the database layer as well as the UI. Permissions for the RPC are service-role only.
- Postgres trigger limits pending account submissions to 12 outstanding or 8 within an hour (serialized counter).

## Files changed
`app.py`, `auth.py`, `store.py`, `config.py`, `gate5_ui.py`; added `db/015_commissioner_approval_accounts.sql`; updated authentication and warm-worker tests; added `tests/test_v116_account_controls.py`; new installation and release notes.

## Verification
- 102 targeted tests passed with offline SDK stubs; 7 real SDK wire tests deselected because Supabase/PostgREST/Streamlit SDKs aren't installed in the audit environment.
- `python -m compileall` passed for the changed files.
- `python release_guard.py` passed.
- SQL was **not** run against live Supabase; DB/RPC behavior and real UI need production smoke tests after installing in documented order.

## Caveat
Do not roll back to v1.0.15 application code alone after running migration. v1.0.15 ignores `account_status` and would bypass the pending gate. All database changes are scoped to the shared project's `pickem` schema; Yahtzee is unchanged.
