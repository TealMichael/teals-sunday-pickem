# Teal's Sunday Pick'em — v1.0.8 Pick'em Pulse
**Release date:** October 16, 2026  
**Baseline:** v1.0.7-hotfix7.19 (September 28, 2026)  
**Supersedes:** the canceled, **never-deployed** v1.0.8 Awards/Cups/Cards proposal. That feature is **not** included here.

## What's new
- **Compact Pick'em Pulse:** One lightweight card in existing Sunday views; no new tabs or social feed.
- **Personalized pregame hype:** Uses only historical FINAL weekly results. Appears on Sunday home only after all five picks are ready and there are no unresolved required backups/unavailable players. Never shown in the picker.
- **One measurable personal goal:** Beat your prior score, beat your past average, or finish Top 5 (for first-time entrants). No bonus points or changes to standings.
- **What You Missed:** During Sunday, compares today's rank/score to a small saved check-in when available. Otherwise shows accurate current status and the next nearby rival. Refreshes along with existing live results. A check-in is saved server-side on first access and periodically while the page is open; the comparison is deliberately framed as a previous check-in, not a complete real-time activity history.
- **Final wrap-up:** The same card summarizes your finalized rank, fantasy score, and personal goal status.
- **One-tap reactions:** Below existing standings, a **collapsed** '👏 Cheer someone on' panel offers 🔥 😂 👏 👀 after lock. Each player can have only **one active reaction per week**, and can change/remove it. No comments, no messaging, no self-reactions.

## Compatibility and privacy
- Unchanged: existing scoring rules, lineup submission/locking/backups, NFL refresh pipeline, scheduled GitHub Actions, AWTRIX clock, Tuesday newsletter, Season, History and Profile navigation.
- Server-authenticated player UUIDs are used for check-ins and reactions; no public database credentials or new data sources.
- Uses existing `pickem.app_meta` with **no SQL migrations or secret changes**. No new dependency packages.
- Does not save roster information in check-ins. Does not reveal private selections before lineup lock.
- If optional Pulse storage/lookup is unavailable, lineup selection and live scoring still proceed normally; reactions simply become unavailable.

## Test results
- `pytest -q`: **373 passed** (356 baseline + 17 new tests).
- `python -m compileall -q .`: PASS.
- `python release_guard.py`: PASS.
- Live Streamlit/Supabase/AWTRIX checks require verification in the deployed environment. These local automated tests do **not** confirm live deployment.

## Files changed or added
Root (upload to repository root):
- `app.py` — version-aware warm-deploy reload guards
- `config.py` — v1.0.8 build key
- `store.py` — minimal check-in/reaction access via existing `app_meta`
- `gate4_ui.py` — single postlock/final card + collapsed reaction panel
- `weekly_ui.py` — compact pregame card on ready-lineup home
- `pickem_pulse.py` (new) — pure/factual engagement logic
- `pulse_ui.py` (new) — compact Streamlit rendering and interaction
- `V1_0_8_PICKEM_PULSE.md` (new) — this release note

Existing `tests/` folder:
- `test_v108_pickem_pulse.py` (new) — 17 regression checks

## Release identity
GitHub commit message: `v1.0.8 — add compact Pick'em Pulse and friendly reactions`  
GitHub tag (optional): `v1.0.8-pickem-pulse`

## Post-deploy spot-check
1. Before lineup lock, complete your five; verify **one** compact personal story, no pre-lock reactions, and no changes to the five-position picker.
2. From a different phone/account after lock, verify rankings remain accurate, reactions save, and another participant's reaction count updates after reload.
3. Confirm that you can change and remove your one reaction and cannot react to yourself.
4. Reopen the app later and confirm 'What You Missed' only states changes grounded in the saved checkpoint; new users get a neutral status.
5. After Monday FINAL, verify the final goal status, existing recap, History, and Tuesday newsletter.
6. Run Commissioner's Test Clock and confirm the AWTRIX broadcast works as before.

**Rollback:** In GitHub, revert the two upload commits in reverse order (test commit, then root code commit), or restore the prior Hotfix 7.19 files. No SQL rollback is necessary; optional `app_meta` rows can remain harmlessly dormant. Do not delete or reset user scores or lineups.
