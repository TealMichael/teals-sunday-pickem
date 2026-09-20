# Hotfix 7.16 — Optional Commissioner-message melodies

**Scope:** A single, opt-in, week-scoped melody choice beneath the three existing Commissioner message controls. Preloaded presets: Happy Birthday, Jingle Bells, Twinkle Twinkle Little Star, Ode to Joy, and Celebration Chime. Select which ONE message (Welcome, Party, or Custom) gets the sound. **OFF by default**. When the selected message recurs, the short tune plays again; there is no once-per-day restriction or sound loop inside one announcement.

## Isolation / non-regressions

- The *existing* `pickem.clock_feed` SQL function is not modified. New `db/011_optional_commissioner_melodies.sql` installs a separate `pickem.clock_message_melodies` week-scoped table and changes ONLY its **public wrapper** `public.pickem_clock_feed` to append an allowlisted `rtttl` field for a selected, enabled, nonblank Commissioner message. It calls `pickem.clock_feed` first and returns the original payload otherwise. Token verification, rich text, prelock privacy, event IDs, live NFL scoring, timing, Test Clock, and acknowledgements stay in the old function.
- `awtrix/PickemSunday.ax` reads the optional field on **manual** non-test announcements only and passes `soundRtttl` to `notify` once. If firmware rejects the sound or the field is absent, it retries the exact same notification WITHOUT sound. Existing event deduplication and ack remain unchanged. It makes **no extra HTTP requests**.
- The Streamlit changes are confined to the Commissioner Clock form and tiny version/reload markers: `gate5_ui.py`, `app.py`, `config.py`. New `clock_melodies.py` reads/writes ONLY the new music table, never original message settings, scoring, player accounts, or lineups. The existing `store.py`, `clock_broadcast.py`, NFL refresh, actions, and other clock scripts are not changed.
- If optional SQL is not installed/unavailable, the melody controls are disabled and original text messages can still be saved.
- The user's actual physical AWTRIX hardware/firmware is not accessible to automated tests, so a live sound check is required after installation.

## Order matters

1. **Supabase first:** run `db/011_optional_commissioner_melodies.sql` in the football project's Supabase SQL Editor. The SQL transaction is safe to rerun, and the existing clock script ignores the extra optional JSON field.
2. **GitHub second:** upload the CONTENTS of `UPLOAD_TO_GITHUB/` into the existing repo ROOT, replacing existing files. The SQL file being committed to GitHub does **not** execute it in Supabase.
3. **Physical AWTRIX third:** replace ONLY the installed *Pickem Sunday* headless script with the NEW `awtrix/PickemSunday.ax` (also downloadable via Commissioner → Clock → One-time clock setup after redeploy). Preserve existing Supabase URL, publishable key, clock token and poll setting. **Do not rotate the clock token**, and do not reinstall the Class Schedule or Daily Fact Challenge scripts.
4. In Commissioner → Clock, turn on **Play a melody with a Commissioner message**, select which one, choose Happy Birthday (or another preset), make sure that message itself is enabled and nonblank, then Save Sunday Clock Messages. Existing **Test Clock** checks the connection, but its synthetic test messages intentionally do not play the melody. The next real selected Commissioner-message ticker will play it. Prelock messages depend on the existing alternating rotation; after 1 PM the Commissioner slot is :55 each hour, and multiple enabled messages rotate across those slots.

**Rollback:** Uncheck the melody checkbox and Save. If there is any unexpected clock-script behavior, reinstall the prior `PickemSunday.ax` from your previous release; the new SQL/table can remain with melodies OFF and original feed behavior preserved.

**Commit:** `v1.0.7 feature — optional Commissioner melodies without changing Sunday scoring`

**Tag:** `v1.0.7-hotfix7.16`

**Supabase SQL:** YES — manual execution required. **AWTRIX script:** YES — replace Pickem Sunday only. **GitHub Actions workflow:** NO changes. **Existing token:** retain; do not rotate.
