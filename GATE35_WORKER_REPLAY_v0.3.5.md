# v0.3.5 — Gate 3.5 Production-Environment Replay

The Streamlit Cloud preseason replay exposed an environment-specific ESPN HTTP failure.
This patch moves the real-provider replay into GitHub Actions, which is the same environment
used by scheduled Sunday scoring. Commissioner mode now opens the workflow runner and reads
the latest successful replay result from `pickem.data_runs`.

No SQL, Supabase, or secret changes are required.
