# v0.1.6 — Gate 1 Interaction + Theme Hotfix

## Fixes
- Removes the double-click behavior on Sign In, Sign Out, and Commissioner actions by mounting the remembered-login browser bridge only when a restore or explicit browser write/delete is actually needed.
- Blocks clickable UI while a queued remembered-login browser command is awaiting acknowledgement, preventing a hidden component rerun from consuming the first click.
- Hardens the app's intentionally light visual theme so phones set to dark system mode still render Pick'em consistently and legibly.

## No changes
- No SQL migration.
- No Supabase settings changes.
- No Streamlit secrets changes.
- No player PIN/session format changes.
