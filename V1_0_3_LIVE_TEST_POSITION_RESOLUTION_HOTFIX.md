# v1.0.3 Commissioner Live Test — Position Resolution Hotfix

Scope: Commissioner Diagnostics only.

The Wednesday dress rehearsal previously discarded ESPN scoring rows when an arbitrary midweek player's live ESPN position was blank and the cached Sleeper identity could not resolve a Pick'em position. This made the diagnostic look like it was receiving only rushing data even though production scoring itself does not use ESPN position as a gate.

The hotfix:
- scores every parsed ESPN row that contains a Pick'em-relevant stat;
- keeps exact team+normalized-name matching visible as the production-key check;
- uses cached position first when available, ESPN position second, and a broad diagnostic role only for display when neither is available;
- adds Passing / Rushing / Receiving / Kicking category proof so live categories can be verified independently of position metadata;
- remains read-only and Commissioner-only.

No production scoring, public UI, lineup, auth, Supabase schema, SQL, NFL refresh workflow, or standings logic changed.
