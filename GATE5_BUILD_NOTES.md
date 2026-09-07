# v0.5.0 — Gate 5 Commissioner Controls

Gate 5 adds the production Commissioner dashboard without changing player-lineup rules or the Gate 3/4 scoring architecture.

## Commissioner dashboard
- Week overview: registered players, lineups ready, players needing a lineup, NFL data state, lock time, and last refresh.
- Missing/incomplete lineup names are surfaced directly.
- Manual **Refresh NFL Data Now** uses the same Gate 3 schedule/injury/live-score paths used by production automation.
- **Generate Again** is available only after the scheduled Tuesday open and only while the real pool is still unpublished.
- **Reconcile / Finalize Now** is available only after the universal lock; the existing reconciliation code still refuses unsettled games.

## Players & PINs
- Lists every registered player and current-week lineup status.
- Commissioner chooses a new 4-digit replacement PIN.
- Existing PIN is never readable.
- Reset hashes the new PIN with the normal PBKDF2 + server pepper path and revokes remembered-device sessions.
- No rename/deactivate controls were added.

## Corrections
### Emergency Player Pool Override
- Available only before Sunday 1:00 PM ET.
- Replacement must be hidden, same-position, schedule-eligible, and not OUT.
- Shows affected lineup count and names before confirmation.
- If the outgoing player is a starter, that pick is removed and the lineup becomes incomplete so the user must repick.
- If the outgoing player is an emergency backup, the backup is cleared.
- Commissioner still cannot directly edit anyone's lineup.

### Manual Score Override
- Available only after Sunday 1:00 PM ET.
- Manual score stays authoritative through Gate 3 automatic refreshes because the existing scoring pipeline already respects `manual_score_override`.
- Clearing restores the provider score from `player_week_stats`.
- If the week is already FINAL, applying/clearing automatically rebuilds archived weekly results so season points stay consistent.

## Diagnostics
- Gate 3 data check
- Gate 3 scoring diagnostic
- Gate 3.5 GitHub replay result
- Gate 4 Live Sunday demo

## Database
No new SQL migration is required. Gate 5 deliberately reuses server-only fields/tables created in Gates 1–4, including `data_runs` for Commissioner audit entries.
