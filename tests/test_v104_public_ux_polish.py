from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v104_version_and_weekly_ui_reload_guard():
    assert 'APP_VERSION = "1.0.7"' in (ROOT / "config.py").read_text("utf-8")
    weekly = (ROOT / "weekly_ui.py").read_text("utf-8")
    app = (ROOT / "app.py").read_text("utf-8")
    assert "WEEKLY_UI_SCHEMA_VERSION = 8" in weekly
    assert 'getattr(_weekly_ui, "WEEKLY_UI_SCHEMA_VERSION", 0) < 8' in app


def test_first_time_onboarding_explains_core_scoring_and_where_to_find_rules():
    text = (ROOT / "weekly_ui.py").read_text("utf-8")
    for needle in [
        "How Teal's Sunday Pick'em works",
        "Five picks. One Sunday. Most fantasy points wins the week.",
        "**Passing:** 1 pt / 25 yds · 4 / TD · −2 / INT",
        "**Rushing & receiving:** 1 pt / 10 yds · 6 / TD · +0.5 / reception",
        "**Kicker:** 3 / made FG · 1 / made XP",
        "Questionable player? Set a backup.",
        "Lock Sunday at 1:00 PM ET.",
        "Profile → How to Play & Scoring",
    ]:
        assert needle in text


def test_profile_rules_are_labeled_as_scoring_reference():
    text = (ROOT / "gate4_ui.py").read_text("utf-8")
    assert 'with st.expander("How to Play & Scoring")' in text
    assert "Passing: 1/25 yds, 4/pass TD, -2/INT" in text
    assert "Kicker: every made FG 3, made XP 1, misses 0" in text


def test_valid_review_keeps_save_immediately_below_clickable_lineup():
    text = (ROOT / "weekly_ui.py").read_text("utf-8")
    start = text.index("def _review(")
    end = text.index("def _open_home(", start)
    review = text[start:end]
    assert review.index("_render_review_editable_lineup(picks, pool_by_id)") < review.index('st.button("SAVE MY LINEUP"')
    assert "Need to make a change?" not in review
    assert 'st.button(f"Change\\n{pos}"' not in review


def test_public_ux_polish_does_not_change_scoring_or_nfl_refresh_contract():
    scoring = (ROOT / "nfl_scoring.py").read_text("utf-8")
    workflow = (ROOT / ".github/workflows/nfl-refresh.yml").read_text("utf-8")
    assert '("field_goals_made", fg_made, fg_made * 3.0' in scoring
    assert 'cron: "7,17,27,37,47,57 12 * * 2"' in workflow
