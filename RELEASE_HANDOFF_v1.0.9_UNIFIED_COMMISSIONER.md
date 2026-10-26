# Teal's Sunday Pick'em — v1.0.9

## Unified Commissioner Login + Simplified Dashboard

Release for installation **after NFL Sunday**, starting from the uploaded
v1.0.8-hotfix8.1 source archive. Nothing has been pushed or deployed live.

### What changes

- Mike T. retains his normal player identity and five picks.
- His account gains a fifth bottom-navigation destination, **Commish**.
- The first visit asks for the existing six-digit Commissioner PIN. Approval
  persists for that remembered player session/device. Each new device needs its
  own approval. A login without "Keep me signed in" has session-only approval.
- Approvals are server-verified against permanent player ID, valid session
  token, revocation, and expiry; checking a navigation label alone is never
  sufficient to access Commissioner tools.
- The first successful approval creates the one-time link in existing protected
  `pickem.app_meta`. No manual SQL, new table, or new secret is required.
- Emergency username/PIN administration stays accessible from the signed-out
  screen as a recovery fallback, not the daily workflow.
- The Commissioner Home screen offers current-week status, Refresh NFL Data,
  Test Clock, and entry points to all six complete existing tool sections.

### Unchanged and protected

- All four navigation destinations for everyone else.
- Saved lineups, scoring, player pool immutability, Sunday 1 PM ET lock, results,
  and history.
- Tuesday pool generation, live NFL sync, Monday finalization, and GitHub
  Actions scheduling.
- AWTRIX broadcast scripts and automatic cadence, commissioner messages,
  newsletter output, diagnostics, and isolated demos.

### Browser upload workflow

1. Wait until Sunday's game activity is finished. Keep the original archive as
   a rollback copy.
2. Extract `Teals_Sunday_Pickem_v1.0.9_BROWSER_UPLOAD.zip` on your Mac.
3. In your `teals-sunday-pickem` GitHub repository, use **Add file → Upload files**
   to replace the root-level files from the extracted bundle. Upload the new
   `commissioner_access.py` in the same root folder as `app.py`.
4. Upload `tests/test_v109_unified_commissioner.py` to the repository's `tests`
   directory (or drag in the enclosing folder if your browser preserves paths).
5. Commit: **v1.0.9 — Link Mike T. to Commissioner and simplify admin dashboard**
6. Confirm GitHub Actions Quality Gate passes, then confirm the Streamlit
   app reports version `1.0.9`.
7. Optional tag: `v1.0.9`. Do not upload either ZIP file as though GitHub will
   extract it automatically.

### First-time smoke test

1. Sign in normally as **Mike T.** with the current four-digit player PIN and
   **Keep me signed in this season** selected.
2. Confirm five bottom tabs, including **Commish**. Other accounts should
   still have only the original four.
3. Open Commish and enter the existing **six-digit Commissioner PIN once**.
   Do not enter that PIN in GitHub, the source code, or chat.
4. Confirm the Home status and open each of the six tool sections. Inspect
   existing controls without firing live refresh, scoring, or reset actions
   unnecessarily.
5. Return to Sunday and Profile without signing out. Reopen Commish and
   refresh the page: it should not request the admin PIN again on that device.
6. Repeat on another trusted device: it should ask for the Commissioner PIN
   once on that separate device.
7. Verify your original lineup and league standings are unchanged.

### Verification before packaging

- `386 passed` in the complete automated Python test suite.
- New security tests cover wrong PIN, cross-account access, per-device trust,
  tampered/expired/revoked sessions, transient approvals, and PIN throttling.
- Python compilation and `release_guard.py` both pass.

Rollback: restore the previous GitHub revision or upload the original v1.0.8
source files. The small role-link records in `pickem.app_meta` are inert to old
builds and do not change player or scoring data.
