# Teal's Sunday Pick'em v1.0.7 Hotfix 7.9.1

## Newsletter warm-deploy repair

Hotfix 7.9 added the Tuesday Text Newsletter, but the existing Streamlit worker could retain the older `SupabaseStore` class because the Store schema generation marker was not advanced. The Newsletter tab would load finalized Week 1 data, then fail when it reached the newly added newsletter settings methods.

This repair:
- advances the Store generation marker so warm workers reload the current Store class;
- advances the Commissioner UI generation marker so the current Newsletter UI is always bound after deploy;
- adds method-presence guards for `get_app_meta` and `set_app_meta`;
- makes newsletter settings reads/writes non-fatal so a temporary settings issue can never hide the finalized recap;
- leaves scoring, lineups, pools, lock logic, NFL refresh, ticker/AWTRIX, and finalized results unchanged.

Validation: 264 tests passed; Python compilation passed; release guard passed.
