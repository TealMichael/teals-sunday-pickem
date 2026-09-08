# v1.0.3 Picker Rerun Hotfix

## Why
The earlier picker-speed hotfix correctly removed the Supabase write from the initial player tap, but each tap still caused two Streamlit script passes: the button interaction rerun plus an explicit `st.rerun()` after staging the local selection. That extra rerun could make the checkmark feel slightly delayed even with no database write.

## Change
- Player-card taps now use Streamlit button callbacks so the pending starter/backup is staged before the normal interaction rerun.
- Removed the explicit second rerun and selection toast from starter/backup card taps.
- The selection remains local until Next.
- Next remains the only persistence point for the staged position.
- Weekly UI reload schema bumped to 5 so Streamlit Cloud cannot retain the previous picker module after deploy.

## Protected behavior unchanged
- Supabase write still occurs only on Next.
- Lock enforcement, eligibility validation, emergency-backup rules, scoring, NFL sync, auth, SQL, and GitHub workflows are unchanged.

## Verification
- pytest: 152/152 PASS
- Full Week Rehearsal: 9/9 PASS
- compileall: PASS
- release_guard: PASS
