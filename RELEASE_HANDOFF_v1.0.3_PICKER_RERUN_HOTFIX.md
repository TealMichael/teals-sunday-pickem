# Release Handoff — v1.0.3 Picker Rerun Hotfix

## Baseline
`Teals_Sunday_Pickem_v1.0.3_Final_Full_PICKER_SPEED_HOTFIX.zip`

## Scope
One remaining picker responsiveness issue only.

## Finding
The first speed hotfix removed Supabase writes from player-card taps, but the tap path still performed an unnecessary second Streamlit rerun. A native Streamlit button click already triggers a rerun; the code then called `st.rerun()` again solely to show the newly staged checkmark.

## Fix
Player-card buttons now use `on_click` callbacks to stage the starter/backup before Streamlit's normal interaction rerun. The checkmark therefore appears after one script pass instead of two. No save occurs until Next.

## Files changed from the prior hotfix
- `weekly_ui.py`
- `app.py` (module reload guard only)
- `tests/test_v103_picker_speed_hotfix.py`
- `tests/test_v103_launch_polish.py`
- `tests/test_v102_sunday_recap.py` (reload-schema expectation only)
- this handoff / hotfix note

## Verification
- 152/152 pytest PASS
- 9/9 Full Week Rehearsal PASS
- Python compile PASS
- release_guard PASS

## No changes
No scoring, store/Supabase persistence code, SQL, NFL provider/sync logic, auth, Tuesday publish workflow, or Quality Gate workflow changes.

## Next
Phone-check one player tap. Expected behavior: immediate-ish local highlight/checkmark; any network wait should occur on Next, not on the player tap. Then freeze for the Wednesday live-scoring dress rehearsal.
