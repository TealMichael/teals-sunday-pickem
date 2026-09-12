# v1.0.7 Hotfix 7.2 — Final Sunday Freeze Hardening

This is a narrow pre-Sunday freeze fix, not a feature release.

## Fixed
- Preserved starters can survive later pool replacement exactly as Hotfix 3 intended while a now-invalid emergency backup can still be cleared before lock.
- The database guard now validates Sunday schedule eligibility for every newly selected starter and emergency backup.
- Injury replacement cannot promote a hidden player whose game is no longer Sunday-eligible.
- A Questionable starter is not considered backup-ready when the saved emergency backup's game has become ineligible.
- The normal visible pool query carries schedule eligibility into the app's pre-save validation.

## Deliberately unchanged
- scoring and kicker rules
- 1:00 PM universal lock time
- live scoring/provider logic
- GitHub refresh cadence and recovery timing
- AWTRIX/Clock Hotfix 7.1 code and physical clock configuration
- auth/PIN behavior
- published-pool immutability

## Install
1. Upload the GitHub patch and wait for the Quality Gate to pass.
2. Run `db/011_preserved_lineup_selection_guard.sql` once in Supabase SQL Editor.
3. No AWTRIX reinstall is required.

After that, freeze the code for Week 1 unless a concrete production defect appears.
