# Gate 5 Hotfix v0.5.2

## Week refresh UI cleanup
- Removes the in-layout NFL refresh spinner that caused Streamlit stale widgets to appear as a duplicated/ghosted Week panel during the network call.
- Uses a non-layout toast while the refresh runs, followed by the persistent success banner already added in v0.5.1.
- Clarifies Manual Score Override copy: tools appear after the Tuesday pool publishes, but applying corrections remains locked until Sunday at 1:00 PM ET.
- No scoring, NFL provider, Supabase, authentication, lineup, or lock behavior changed.
