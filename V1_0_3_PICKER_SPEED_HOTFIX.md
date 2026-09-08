# v1.0.3 Picker Speed Hotfix

**Date:** September 8, 2026

## Problem
The v1.0.3 Select → highlight → Next flow still called `store.save_pick()` as soon as a player card was tapped. That meant the visible checkmark waited on a Supabase write even though the user had not pressed Next yet.

## Fix
- Card tap: local Streamlit session-state selection only.
- Next/Return: the confirmed position is written once to Supabase, then navigation advances.
- Questionable starter + emergency backup: both are staged locally and saved together.
- Unchanged saved choice + Next: no redundant upsert.
- Back: discards the staged, unsaved choice.
- Builder lineup snapshot TTL: 300 seconds while actively choosing, reducing unnecessary lineup reads during the five-pick flow.

## Explicitly unchanged
Scoring, NFL sync/provider code, player-pool rankings, Tuesday publication retry workflow, lock rules, emergency activation rules, auth/PINs, Supabase schema, season points, standings, and recap logic.
