# Release Handoff — Teal's Sunday Pick'em v1.0.3

## Exact baseline
Built from `Teals_Sunday_Pickem_v1.0.2_Final_Full_SIGNUP_HOTFIX.zip`, which already contained the v1.0.2 Sunday Status + Weekly Recap release, the `.streamlit/config.toml` CI fix, and the signup emoji/PIN UX hotfix.

## Why v1.0.3 exists
On Tuesday, September 8, the real Week 1 pool successfully published when manually triggered and the full real lineup flow passed on a phone: build five, save, close/reopen, and edit. Two improvements were then approved before the Wednesday live-scoring rehearsal:
1. Replace tap-and-instant-advance with **Select → highlight → Next**.
2. Add redundant Tuesday-noon publish attempts because GitHub's scheduled run did not arrive near noon.

## v1.0.3 decisions locked
- A player tap saves immediately but does **not** navigate.
- Selected starter/backup remains visibly highlighted.
- Next controls navigation only.
- Questionable starter requires the emergency-backup step only when a valid backup is not already stored.
- Tuesday publish retry schedule: 12:07 / :17 / :27 / :37 / :47 / :57 PM ET.
- Existing `run_auto()` publication guard remains the source of truth, so retries are idempotent.
- Manual GitHub `publish` remains the backup path.

## Protected behavior — do not drift
- Five positions: QB, RB, WR, TE, K
- Five visible players per position
- Sunday only; universal 1:00 PM ET lock
- Kicker: 3 per made FG, 1 per XP, misses 0, no negative points
- Questionable emergency-backup rules unchanged
- OUT starter activates stored same-position backup only under the existing rules
- Incomplete positions score 0
- Weekly/season tie behavior unchanged
- NFL/provider → raw stats → score breakdown → standings pipeline unchanged
- No database/schema/auth changes in v1.0.3

## Files intentionally changed
- `.github/workflows/nfl-refresh.yml`
- `app.py`
- `config.py`
- `ui.py`
- `weekly_ui.py`
- `README.md`
- version/contract tests plus new `tests/test_v103_launch_polish.py`
- v1.0.3 release/test/handoff documentation

## Verification
- Automated tests: **145/145 PASS**
- Full-week rehearsal: **9/9 PASS**
- Python compile: **PASS**
- Release guard: **PASS**
- SQL migrations: unchanged from v1.0.2 baseline
- `nfl_scoring.py`, `nfl_sync.py`, `store.py`, `auth.py`, `security.py`: unchanged
- Quality-gate workflow: unchanged

## Next planned gate
Wednesday night: Commissioner-only live-game dress rehearsal using the real live provider/scoring pipeline without altering Week 1 public standings. If green, Thursday may add only scoring-breakdown presentation polish.
