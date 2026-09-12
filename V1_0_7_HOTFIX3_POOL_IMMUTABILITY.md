# v1.0.7 Hotfix 3 — Published Pool / Saved Lineup Protection

## Why this release exists
A Friday injury refresh replaced a visible player from the published weekly pool. The old implementation intentionally deleted any saved starter pick that referenced the outgoing player and cleared the lineup confirmation. That could turn a completed 5/5 lineup into 4/5 without the player doing anything.

## Fixes
- Published ranked pools are now frozen against accidental re-publication/re-ranking.
- Automatic OUT-player replacements preserve every already-saved starter pick.
- Schedule-driven replacements preserve every already-saved starter pick.
- Commissioner pool overrides preserve every already-saved starter pick.
- Invalid/OUT emergency backups may still be cleared because they can no longer serve as a backup.
- Hidden outgoing rows referenced by saved lineups are hydrated only for that player's display so their original pick remains visible.
- Hidden outgoing rows do not return to the selectable five.
- An OUT starter with a valid emergency backup remains lineup-ready; the backup can activate under the existing scoring rules.
- An OUT starter without a valid backup remains a 5/5 saved lineup but is flagged for optional replacement before lock; if left unchanged, existing scoring behavior applies.

## Protected areas
No scoring formula changes. No live-score parser changes. No auth changes. No lock-time changes. No changes to the 15-minute Sunday scoring schedule.

## Clock source-of-truth
This full build also records the already-proven AWTRIX RPC repair (public wrappers + pgcrypto search_path) so the full source package no longer regresses to the pre-fix clock script.
