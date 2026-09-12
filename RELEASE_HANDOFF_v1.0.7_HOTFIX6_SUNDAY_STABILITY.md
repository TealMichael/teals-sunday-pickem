# Release Handoff — v1.0.7-hotfix6

Baseline: v1.0.7-hotfix5.

Purpose: last pre-Sunday reliability hardening. This is not a feature release.

The release protects live scores from regression, makes the public live screen self-refresh, hardens the 1 PM transition, freezes pregame injury eligibility at player kickoff, improves recovery timing, fixes scheduler timing semantics, preserves valid scores through partial provider failures, and prevents warm Streamlit workers from retaining stale hotfix modules.

No database schema change is introduced. Existing Hotfix 5 SQL remains the current DB state. Existing AWTRIX configuration remains current.

Rollback:
Use the v1.0.7 Hotfix 5 full source package if a Hotfix 6 regression is discovered before Sunday. Do not roll back database migrations because Hotfix 6 adds none.

Recommended state after deployment:
Freeze code. On Sunday, perform operational checks rather than feature changes.
