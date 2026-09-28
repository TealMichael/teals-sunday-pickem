# v1.0.7 Hotfix 7.19 — Smarter Tuesday Newsletter Recap

## What changed
The Tuesday copy/paste newsletter now reads like a short weekly recap instead of a raw data dump.

- Keeps the full weekly standings so every participant can find their finish.
- Formats weekly ties as `1T`, `3T`, etc.
- Replaces the permanent Perfect 5 line with one optional Commissioner-style sentence.
- The Commissioner sentence appears only when the data contains a genuinely notable story.
- Shows the current app season Top 5 instead of only the season leader.
- Keeps the next-week lineup link at the bottom.

## Commissioner story logic
The recap selects at most one data-backed story, prioritizing:
1. a shared weekly championship;
2. back-to-back weekly wins;
3. a new season leader;
4. a winner within 10 points of the perfect legal lineup;
5. a 15+ point weekly winning margin;
6. five season leaders separated by 5 points or fewer;
7. a 4+ place jump into the season Top 5;
8. the inaugural Week 1 winner.

If none of those conditions is interesting that week, the Commissioner line is omitted rather than forcing filler.

## Safety / unchanged areas
No Supabase migration.
No AWTRIX script change.
No clock SQL change.
No scoring formula change.
No NFL refresh change.
No lineup, lock, pool, injury, authentication, or season-points change.

The newsletter still reads finalized archived results and the same app-owned season standings.

## Deployment hardening
- `NEWSLETTER_LOGIC_SCHEMA_VERSION` advances to 2.
- `GATE5_UI_SCHEMA_VERSION` advances to 9.
- `APP_BUILD_VERSION` advances to `1.0.7-hotfix7.19`.
- Warm Streamlit workers explicitly reload the new newsletter module.
- The newsletter source fingerprint now includes season results so a season-standings correction regenerates the automatic text.

## Validation
- Full reconstructed regression suite: 345 passed.
- `release_guard.py`: PASS.
- Python compilation: PASS.
