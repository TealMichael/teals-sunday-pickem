from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import secrets
from typing import Any, Mapping

from gate4 import add_zero_point_players, build_season_standings, build_storylines, build_weekly_leaderboard

UTC = timezone.utc
CLOCK_SNAPSHOT_VERSION = 1
CLOCK_MESSAGE_MAX = 420
MANUAL_MESSAGE_MAX = 240


def new_clock_token() -> tuple[str, str, str]:
    """Return a new scoped clock token, its SHA-256 hash, and a short hint."""
    token = secrets.token_urlsafe(32)
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    hint = token[-6:]
    return token, digest, hint


def _clean(text: Any, limit: int = CLOCK_MESSAGE_MAX) -> str:
    value = " ".join(str(text or "").split()).strip()
    return value[:limit]


def _score(row: Mapping[str, Any]) -> float:
    manual = row.get("manual_score_override")
    value = manual if manual is not None else row.get("score_total")
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _whole(value: Any) -> str:
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        return "0"
    return str(int(number)) if number.is_integer() else f"{number:g}"


def _first_number(stats: Mapping[str, Any], *keys: str) -> float:
    for key in keys:
        value = stats.get(key)
        if value is None or value == "":
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return 0.0


def stat_summary(stats: Mapping[str, Any], *, max_parts: int = 4) -> str:
    """Create a compact AWTRIX-friendly stat ingredient summary."""
    values = [
        ("PASS YDS", _first_number(stats, "passing_yards", "pass_yds")),
        ("PASS TD", _first_number(stats, "passing_tds", "pass_td")),
        ("INT", _first_number(stats, "interceptions", "passing_interceptions", "int")),
        ("RUSH YDS", _first_number(stats, "rushing_yards", "rush_yds")),
        ("RUSH TD", _first_number(stats, "rushing_tds", "rush_td")),
        ("REC", _first_number(stats, "receptions", "rec")),
        ("REC YDS", _first_number(stats, "receiving_yards", "rec_yds")),
        ("REC TD", _first_number(stats, "receiving_tds", "rec_td")),
        ("FG", _first_number(stats, "field_goals_made", "fg_made")),
        ("XP", _first_number(stats, "extra_points_made", "xp_made", "pat_made")),
    ]
    parts = [f"{_whole(value)} {label}" for label, value in values if value != 0]
    return " + ".join(parts[:max_parts])


def _weekly_text(leaderboard: list[dict[str, Any]], *, final: bool) -> str:
    if not leaderboard:
        return ""
    label = "WEEK FINAL" if final else "PICK'EM LIVE"
    rows = [f"{int(row.get('rank') or 0)} {row.get('nickname') or 'Player'} {float(row.get('score') or 0):.1f}" for row in leaderboard]
    return _clean(label + " • " + " • ".join(rows))


def _season_text(standings: list[dict[str, Any]], nfl_week: int) -> str:
    if nfl_week < 2 or not standings:
        return ""
    rows = [f"{int(row.get('rank') or 0)} {row.get('nickname') or 'Player'} {int(row.get('season_points') or 0)} PTS" for row in standings]
    return _clean("SEASON STANDINGS • " + " • ".join(rows))


def _live_games_text(games: list[dict[str, Any]]) -> str:
    live = [row for row in games if str(row.get("game_status") or "").upper() == "LIVE"]
    live.sort(key=lambda row: str(row.get("kickoff_at") or ""))
    if not live:
        return ""
    bits: list[str] = []
    for game in live:
        away = str(game.get("away_team") or "AWAY")
        home = str(game.get("home_team") or "HOME")
        away_score = game.get("away_score") if game.get("away_score") is not None else 0
        home_score = game.get("home_score") if game.get("home_score") is not None else 0
        period = game.get("period")
        clock = str(game.get("game_clock") or "").strip()
        suffix = f" Q{period}" if period else " LIVE"
        if clock:
            suffix += f" {clock}"
        bits.append(f"{away} {away_score} {home} {home_score}{suffix}")
    return _clean("NFL LIVE • " + " • ".join(bits))


def _player_updates(pool: list[dict[str, Any]], stats_rows: list[dict[str, Any]]) -> list[str]:
    stats_by_pool = {str(row.get("pool_player_id")): row for row in stats_rows}
    rows: list[tuple[float, str]] = []
    for player in pool:
        if not bool(player.get("is_visible")):
            continue
        if str(player.get("game_status") or player.get("score_status") or "").upper() != "LIVE":
            continue
        score = _score(player)
        if score <= 0:
            continue
        stat_row = stats_by_pool.get(str(player.get("id"))) or {}
        stats = stat_row.get("raw_stats") or {}
        ingredients = stat_summary(stats)
        text = f"PLAYER UPDATE • {player.get('player_name') or 'Player'} • {score:.1f} PTS"
        if ingredients:
            text += f" • {ingredients}"
        rows.append((score, _clean(text)))
    rows.sort(key=lambda item: (-item[0], item[1].casefold()))
    return [text for _, text in rows]


def _pulse_texts(story: dict[str, Any]) -> list[str]:
    rows: list[str] = []
    popular = story.get("most_popular") or {}
    if popular.get("player_name") and int(popular.get("total") or 0) > 0:
        rows.append(_clean(f"PICK'EM PULSE • MOST POPULAR • {popular.get('player_name')} • {int(popular.get('count') or 0)}/{int(popular.get('total') or 0)} LINEUPS"))
    for item in (story.get("went_alone") or [])[:3]:
        if item.get("nickname") and item.get("player_name"):
            rows.append(_clean(f"PICK'EM PULSE • GOING SOLO • {item.get('nickname')} HAS {item.get('player_name')}"))
    for names in (story.get("same_brain") or [])[:2]:
        if len(names) >= 2:
            rows.append(_clean("PICK'EM PULSE • SAME BRAIN • " + " + ".join(names)))
    return rows


def build_clock_snapshot(store, week: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    """Build the compact, read-only Sunday broadcast snapshot from app-owned data."""
    now = (now or datetime.now(UTC)).astimezone(UTC)
    week_id = str(week["id"])
    bundle = store.get_week_public_bundle(week_id, ttl_seconds=0.01)
    leaderboard = build_weekly_leaderboard(bundle)
    registered_players = store.get_registered_players()
    existing_weekly = {str(row.get("player_id")) for row in leaderboard}
    for player in registered_players:
        if str(player.get("id")) not in existing_weekly:
            leaderboard.append({
                "player_id": str(player.get("id")),
                "nickname": str(player.get("nickname") or "Player"),
                "emoji": str(player.get("emoji") or "🏈"),
                "confirmed": False,
                "score": 0.0,
            })
    leaderboard.sort(key=lambda row: (-float(row.get("score") or 0), str(row.get("nickname") or "").casefold()))
    previous_score = None
    current_rank = 0
    for index, row in enumerate(leaderboard, start=1):
        score = float(row.get("score") or 0)
        if previous_score is None or score != previous_score:
            current_rank = index
        row["rank"] = current_rank
        previous_score = score

    story = build_storylines(bundle, [row for row in leaderboard if row.get("lineup_id")])
    results = store.get_weekly_results(season=int(week.get("season") or 0))
    season = add_zero_point_players(build_season_standings(results), registered_players)
    pool = list(bundle.get("pool") or [])
    stats_rows = store.get_player_week_stats(week_id, [str(row.get("id")) for row in pool if row.get("id")])
    final = str(week.get("data_status") or "").upper() == "FINAL"

    registered = len(registered_players)
    confirmed = sum(1 for row in (bundle.get("lineups") or []) if row.get("confirmed_at"))
    readiness = _clean(f"SUNDAY PICK'EM • {confirmed}/{registered} LINEUPS READY • PICKS LOCK 1 PM ET") if registered else "SUNDAY PICK'EM • PICKS LOCK 1 PM ET"

    champions = [row for row in leaderboard if int(row.get("rank") or 0) == 1]
    champion_text = ""
    if final and champions:
        names = " + ".join(str(row.get("nickname") or "Player") for row in champions)
        champion_text = _clean(f"WEEK {int(week.get('nfl_week') or 0)} CHAMPION • {names} • {float(champions[0].get('score') or 0):.1f} PTS")

    return {
        "version": CLOCK_SNAPSHOT_VERSION,
        "week_id": week_id,
        "season": int(week.get("season") or 0),
        "nfl_week": int(week.get("nfl_week") or 0),
        "week_label": str(week.get("label") or f"Week {week.get('nfl_week') or ''}"),
        "data_status": str(week.get("data_status") or "WAITING").upper(),
        "generated_at": now.isoformat(),
        "readiness": readiness,
        "weekly": _weekly_text(leaderboard, final=final),
        "season_text": _season_text(season, int(week.get("nfl_week") or 0)),
        "live_games": _live_games_text(list(bundle.get("games") or [])),
        "player_updates": _player_updates(pool, stats_rows),
        "pulses": _pulse_texts(story),
        "champion": champion_text,
    }


def refresh_clock_snapshot(store, week: dict[str, Any]) -> dict[str, Any] | None:
    """Refresh the server-side clock snapshot if the optional v1.0.7 schema exists."""
    try:
        payload = build_clock_snapshot(store, week)
        store.upsert_clock_snapshot(str(week["id"]), payload)
        return payload
    except Exception:
        # Clock broadcasting is intentionally optional and may never take the
        # player app or NFL automation down if migration/setup is incomplete.
        return None
