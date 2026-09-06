# v0.1.8 — Gate 1 Final UI/Auth Polish

This patch addresses the three remaining real-device Gate 1 polish issues:

1. Removes the brief duplicated/"mirrored" sign-in form by processing successful sign-in in a Streamlit callback before the next page render. The remembered-device write now finishes while the signed-in home screen is already visible instead of stopping between the form and home screen.
2. Forces secondary buttons (including Sign Out) to remain white with dark text even when the phone is using system dark mode.
3. Adds safe top spacing and line-height to the hero eyebrow so "Sunday football with friends" cannot be clipped at the top edge.

No SQL changes, Supabase changes, or Streamlit secret changes are required.

## GitHub files to replace
- `app.py`
- `ui.py`
- `config.py`

## Commit
`v0.1.8 — Gate 1 Final UI/Auth Polish`

## Commit changes
`Removes the brief mirrored sign-in transition, fixes dark-mode secondary buttons, and prevents the hero eyebrow from clipping on mobile.`

## Tag
`v0.1.8`
