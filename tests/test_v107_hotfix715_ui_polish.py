"""UI-only regression coverage for Hotfix 7.15's five accessibility/layout tweaks."""
from __future__ import annotations

import ast
from contextlib import nullcontext
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path
import html

import lineup_reveal
from weekly import POSITIONS, parse_timestamp, picks_by_position

ROOT = Path(__file__).resolve().parents[1]


def _isolated(path: str, name: str, env: dict):
    tree = ast.parse((ROOT / path).read_text("utf-8"))
    func = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name)
    exec(compile(ast.Module(body=[func], type_ignores=[]), path, "exec"), env)
    return env[name]


def test_picker_progress_is_saved_only_read_only_and_marks_current_step():
    progress = _isolated("weekly_ui.py", "_picker_progress_html", {
        "POSITIONS": POSITIONS, "picks_by_position": picks_by_position, "html": html,
    })
    picks = [
        {"position": "QB", "pool_player_id": "a"},
        {"position": "RB", "pool_player_id": "b"},
        {"position": "WR", "pool_player_id": ""},  # pending tap is NOT a saved pick
    ]
    before = deepcopy(picks)
    markup = progress(picks, "WR")
    assert 'aria-label="Step 3 of 5; 2 of 5 picks saved"' in markup
    assert "Step 3 of 5 · 2 saved" in markup
    assert markup.count('class="picker-step') == 5
    assert markup.count('aria-current="step"') == 1
    assert "QB ✓" in markup and "RB ✓" in markup and "WR ✓" not in markup
    assert 'class="picker-step picker-step-current" aria-current="step">WR<' in markup
    assert "onclick" not in markup.lower() and "<button" not in markup.lower()
    assert picks == before
    assert "0 of 5 picks saved" in progress([], "QB")
    assert "5 of 5 picks saved" in progress([
        {"position": pos, "pool_player_id": pos} for pos in POSITIONS
    ], "K")


class FakeStreamlit:
    def __init__(self):
        self.output = []
    def markdown(self, value, **kwargs):
        self.output.append(str(value))
    def caption(self, value, **kwargs):
        self.output.append(str(value))
    def expander(self, value, **kwargs):
        self.output.append("EXPANDER: " + str(value))
        return nullcontext()


def _bundle():
    pool = [{"id": f"{p}-1", "position": p, "player_name": f"{p} Player"} for p in POSITIONS]
    players = [{"id": "a", "nickname": "Mike"}, {"id": "b", "nickname": "Jenny"}]
    lineups = [{"id": "la", "player_id": "a"}, {"id": "lb", "player_id": "b"}]
    picks = [{"lineup_id": f"l{owner}", "position": p, "pool_player_id": f"{p}-1",
              "emergency_pool_player_id": "PRIVATE_BACKUP"}
             for owner in ("a", "b") for p in POSITIONS]
    return {"pool": pool, "players": players, "lineups": lineups, "picks": picks}


def test_reveal_can_split_teaser_and_details_without_leaking_before_lock():
    fake = FakeStreamlit()
    phase = {"value": "open"}
    renderer = _isolated("gate4_ui.py", "_render_lineup_reveal", {
        "st": fake, "week_phase": lambda week: phase["value"],
        "build_lineup_reveal": lineup_reveal.build_lineup_reveal,
        "escape": escape,
    })
    bundle = _bundle()
    original = deepcopy(bundle)
    assert renderer({"id": "w"}, bundle, show_details=False) is None
    assert fake.output == []
    phase["value"] = "locked"
    reveal = renderer({"id": "w", "is_demo": True}, bundle)
    assert reveal is None and fake.output == []
    reveal = renderer({"id": "w"}, bundle, show_details=False)
    teaser = " ".join(fake.output)
    assert "THE 1 PM LINEUP REVEAL" in teaser
    assert "EXPANDER:" not in teaser
    assert "Mike" not in teaser and "Jenny" not in teaser and "PRIVATE_BACKUP" not in teaser
    fake.output.clear()
    renderer({"id": "w"}, bundle, show_summary=False, reveal=reveal)
    details = " ".join(fake.output)
    assert "EXPANDER: See who picked whom" in details
    assert "Mike" in details and "Jenny" in details
    assert "THE 1 PM LINEUP REVEAL" not in details
    assert "PRIVATE_BACKUP" not in details
    assert bundle == original


def test_live_freshness_warning_only_during_actual_live_games():
    check = _isolated("gate4_ui.py", "_live_freshness_state", {
        "parse_timestamp": parse_timestamp, "datetime": datetime, "timezone": timezone,
    })
    now = datetime(2026, 9, 20, 17, tzinfo=timezone.utc)
    live = [{"game_status": "LIVE"}]
    week = {"data_status": "LIVE", "last_data_refresh_at": (now - timedelta(minutes=3)).isoformat()}
    tone, message = check(week, live, now=now)
    assert tone == "fresh" and "Live updates active" in message
    week["last_data_refresh_at"] = (now - timedelta(minutes=10)).isoformat()
    assert check(week, live, now=now)[0] == "delayed"
    week["last_data_refresh_at"] = (now - timedelta(minutes=21)).isoformat()
    assert check(week, live, now=now)[0] == "warning"
    assert "lineup is safe" in check(week, live, now=now)[1]
    assert check(week, [{"game_status": "FINAL"}], now=now)[0] == "quiet"
    assert check({**week, "data_status": "FINAL"}, live, now=now)[0] == "quiet"
    assert check({"data_status": "LIVE"}, live, now=now)[0] == "warning"
    assert check({"data_status": "LIVE"}, [{"game_status": "SCHEDULED"}], now=now)[0] == "quiet"
    assert check(week, ["malformed game"], now=now)[0] == "quiet"


def test_sunday_information_order_has_one_public_bundle_read_and_no_lineup_writes():
    text = (ROOT / "gate4_ui.py").read_text()
    live = text.split("def render_live_sunday(", 1)[1].split("def _render_season_rows", 1)[0]
    teaser = 'reveal = _render_lineup_reveal(fresh_week, bundle, show_details=False)'
    race = '_render_personal_sunday_drama(fresh_week, bundle, leaderboard, str(player.get("id") or ""))'
    standings = 'st.markdown("### Standings")'
    detail = '_render_lineup_reveal(fresh_week, bundle, show_summary=False, reveal=reveal)'
    story = 'with st.expander("More Sunday storylines", expanded=False):'
    assert live.index(teaser) < live.index(race) < live.index(standings) < live.index(detail) < live.index(story)
    assert live.count("get_week_public_bundle(") == 1
    assert "_last_updated(fresh_week, list(bundle.get(\"games\") or []))" in live
    for forbidden in ("save_pick(", "publish_week_pool(", "upsert(", "requests.get("):
        assert forbidden not in live


def test_profile_copy_mobile_nav_and_warm_deploy_guards():
    gate4 = (ROOT / "gate4_ui.py").read_text()
    css = (ROOT / "ui.py").read_text()
    weekly = (ROOT / "weekly_ui.py").read_text()
    app = (ROOT / "app.py").read_text()
    config = (ROOT / "config.py").read_text()
    assert 'See {len(awards) - 4} more achievements' in gate4
    assert "Notifications are not required for Week 1" not in gate4
    assert 'padding:.3rem .4rem !important' in css
    assert 'flex-wrap:nowrap !important' in css
    assert 'font-size:.75rem !important' in css
    assert "color:#52616B !important" in css
    assert 'WEEKLY_UI_SCHEMA_VERSION = 12' in weekly
    assert 'GATE4_UI_SCHEMA_VERSION = 10' in gate4
    assert 'getattr(_weekly_ui, "WEEKLY_UI_SCHEMA_VERSION", 0) < 12' in app
    assert 'getattr(_gate4_ui, "GATE4_UI_SCHEMA_VERSION", 0) < 10' in app
    assert 'APP_BUILD_VERSION = "1.0.7-hotfix7.15"' in config
    assert 'UI_THEME_SCHEMA_VERSION = 3' in css
    assert 'getattr(_ui, "UI_THEME_SCHEMA_VERSION", 0) < 3' in app
    assert 'getattr(_config, "APP_BUILD_VERSION", "") != "1.0.7-hotfix7.15.1"' in app
    # Weekly UI binds Gate 4 functions with "from gate4_ui import ...". A warmed
    # worker must reload Gate 4 first or the Sunday renderer stays stale.
    assert app.index('if _reloaded_automation_recovery or getattr(_gate4_ui, "GATE4_UI_SCHEMA_VERSION", 0) < 10:') < app.index('or _reloaded_gate4_ui')
    assert 'or _reloaded_gate4_ui' in app
