from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import hashlib
import secrets
from typing import Any, Mapping

from gate4 import add_zero_point_players, build_season_standings, build_storylines, build_weekly_leaderboard

UTC = timezone.utc
ET = ZoneInfo("America/New_York")
CLOCK_SNAPSHOT_VERSION = 3
CLOCK_MESSAGE_MAX = 420
MANUAL_MESSAGE_MAX = 240


# AWTRIX rich-text colors. Keep most copy white and use color as an accent so
# long scrolling messages remain easy to read on the 8x32 matrix.
WHITE = "FFFFFF"
TEAL = "2DD4BF"
GOLD = "FFD700"
YELLOW = "FFD60A"
PURPLE = "BF5AF2"
LIGHT_BLUE = "64D2FF"
GREEN = "34C759"
WARNING_ORANGE = "FF9F0A"
RED = "FF453A"
BEARS_ORANGE = "F56600"
BEARS_BLUE = "5B7CFA"

# Readable accent versions of NFL team colors for a black LED-matrix
# background. Very dark official primaries are intentionally brightened.
NFL_TEAM_COLORS = {
    "ARI": "D13C4F", "ATL": "D7193F", "BAL": "9E7CFF", "BUF": "2F74C0",
    "CAR": "00A5B5", "CHI": BEARS_ORANGE, "CIN": "FB4F14", "CLE": "FF3C00",
    "DAL": "5C8EC7", "DEN": "FB4F14", "DET": "0076B6", "GB": "FFB612",
    "HOU": "E03A3E", "IND": "4A90E2", "JAX": "00A5B5", "KC": "E31837",
    "LV": "C4C4C4", "LAC": "00A5E0", "LAR": "4A90E2", "MIA": "00B2A9",
    "MIN": "A78BFA", "NE": "C60C30", "NO": "D3BC8D", "NYG": "4A90E2",
    "NYJ": "32A852", "PHI": "39A895", "PIT": "FFB612", "SEA": "69BE28",
    "SF": "E02020", "TB": "D50A0A", "TEN": "4B92DB", "WAS": "FFB612",
}


def _team_color(team: Any) -> str:
    return NFL_TEAM_COLORS.get(str(team or "").upper(), WHITE)


def _fragment(text: Any, color: str = WHITE) -> dict[str, str]:
    return {"t": str(text or ""), "c": str(color or WHITE).lstrip("#").upper()}


def _rich(parts: list[tuple[Any, str]], limit: int = CLOCK_MESSAGE_MAX) -> list[dict[str, str]]:
    """Return AWTRIX colored-text fragments while enforcing the ticker limit."""
    remaining = int(limit)
    out: list[dict[str, str]] = []
    for raw, color in parts:
        if remaining <= 0:
            break
        value = str(raw or "").replace("\n", " ").replace("\r", " ").replace("\t", " ")
        if not value:
            continue
        piece = value[:remaining]
        remaining -= len(piece)
        normalized_color = str(color or WHITE).lstrip("#").upper()
        if out and out[-1]["c"] == normalized_color:
            out[-1]["t"] += piece
        else:
            out.append(_fragment(piece, normalized_color))
    return out


def _plain_from_rich(parts: list[dict[str, str]], limit: int = CLOCK_MESSAGE_MAX) -> str:
    return _clean("".join(str(part.get("t") or "") for part in parts), limit)


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


def _weekly_rich(leaderboard: list[dict[str, Any]], *, final: bool) -> list[dict[str, str]]:
    if not leaderboard:
        return []
    label_color = GOLD if final else TEAL
    parts: list[tuple[Any, str]] = [("WEEK FINAL • " if final else "PICK'EM LIVE • ", label_color)]
    for idx, row in enumerate(leaderboard):
        rank = int(row.get("rank") or 0)
        nickname = row.get("nickname") or "Player"
        score = float(row.get("score") or 0)
        parts.append((f"{rank} {nickname}", GOLD if rank == 1 else WHITE))
        parts.append((f" {score:.1f}", TEAL))
        if idx < len(leaderboard) - 1:
            parts.append((" • ", WHITE))
    return _rich(parts)


def _weekly_text(leaderboard: list[dict[str, Any]], *, final: bool) -> str:
    return _plain_from_rich(_weekly_rich(leaderboard, final=final))


def _season_rich(standings: list[dict[str, Any]], nfl_week: int) -> list[dict[str, str]]:
    if nfl_week < 2 or not standings:
        return []
    parts: list[tuple[Any, str]] = [("SEASON STANDINGS • ", LIGHT_BLUE)]
    for idx, row in enumerate(standings):
        rank = int(row.get("rank") or 0)
        nickname = row.get("nickname") or "Player"
        points = int(row.get("season_points") or 0)
        parts.append((f"{rank} {nickname}", GOLD if rank == 1 else WHITE))
        parts.append((f" {points} PTS", LIGHT_BLUE))
        if idx < len(standings) - 1:
            parts.append((" • ", WHITE))
    return _rich(parts)


def _season_text(standings: list[dict[str, Any]], nfl_week: int) -> str:
    return _plain_from_rich(_season_rich(standings, nfl_week))


def _live_games_rich(games: list[dict[str, Any]]) -> list[dict[str, str]]:
    live = [row for row in games if str(row.get("game_status") or "").upper() == "LIVE"]
    live.sort(key=lambda row: str(row.get("kickoff_at") or ""))
    if not live:
        return []
    parts: list[tuple[Any, str]] = [("NFL LIVE • ", RED)]
    for idx, game in enumerate(live):
        away = str(game.get("away_team") or "AWAY").upper()
        home = str(game.get("home_team") or "HOME").upper()
        away_score = game.get("away_score") if game.get("away_score") is not None else 0
        home_score = game.get("home_score") if game.get("home_score") is not None else 0
        period = game.get("period")
        clock = str(game.get("game_clock") or "").strip()
        suffix = f" • Q{period}" if period else " • LIVE"
        if clock:
            suffix += f" {clock}"
        parts.extend([
            (away, _team_color(away)),
            (f" {away_score} • ", WHITE),
            (home, _team_color(home)),
            (f" {home_score}{suffix}", WHITE),
        ])
        if idx < len(live) - 1:
            parts.append((" • ", WHITE))
    return _rich(parts)


def _live_games_text(games: list[dict[str, Any]]) -> str:
    # Preserve the historical plain-text fallback exactly; the physical clock
    # prefers live_games_rich when Hotfix 7 is installed.
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


def _player_updates_rich(pool: list[dict[str, Any]], stats_rows: list[dict[str, Any]]) -> list[list[dict[str, str]]]:
    stats_by_pool = {str(row.get("pool_player_id")): row for row in stats_rows}
    rows: list[tuple[float, str, list[dict[str, str]]]] = []
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
        player_name = str(player.get("player_name") or "Player")
        team = str(player.get("team_abbr") or "")
        parts: list[tuple[Any, str]] = [
            ("PLAYER UPDATE • ", YELLOW),
            (player_name, _team_color(team)),
            (" • ", WHITE),
            (f"{score:.1f} PTS", GOLD),
        ]
        if ingredients:
            parts.extend([(" • ", WHITE), (ingredients, WHITE)])
        rich = _rich(parts)
        rows.append((score, player_name.casefold(), rich))
    rows.sort(key=lambda item: (-item[0], item[1]))
    return [rich for _, _, rich in rows]


def _player_updates(pool: list[dict[str, Any]], stats_rows: list[dict[str, Any]]) -> list[str]:
    return [_plain_from_rich(parts) for parts in _player_updates_rich(pool, stats_rows)]


def _pulse_rich(story: dict[str, Any], pool: list[dict[str, Any]]) -> list[list[dict[str, str]]]:
    team_by_name = {
        str(row.get("player_name") or "").casefold(): str(row.get("team_abbr") or "")
        for row in pool
        if row.get("player_name")
    }
    rows: list[list[dict[str, str]]] = []
    popular = story.get("most_popular") or {}
    if popular.get("player_name") and int(popular.get("total") or 0) > 0:
        name = str(popular.get("player_name"))
        rows.append(_rich([
            ("PICK'EM PULSE • MOST POPULAR • ", PURPLE),
            (name, _team_color(team_by_name.get(name.casefold()))),
            (" • ", WHITE),
            (f"{int(popular.get('count') or 0)}/{int(popular.get('total') or 0)}", PURPLE),
            (" LINEUPS", WHITE),
        ]))
    for item in (story.get("went_alone") or [])[:3]:
        if item.get("nickname") and item.get("player_name"):
            name = str(item.get("player_name"))
            rows.append(_rich([
                ("PICK'EM PULSE • GOING SOLO • ", PURPLE),
                (str(item.get("nickname")), PURPLE),
                (" HAS ", WHITE),
                (name, _team_color(team_by_name.get(name.casefold()))),
            ]))
    for names in (story.get("same_brain") or [])[:2]:
        if len(names) >= 2:
            rows.append(_rich([
                ("PICK'EM PULSE • SAME BRAIN • ", PURPLE),
                (" + ".join(names), PURPLE),
                (" • SAME FIVE PICKS", WHITE),
            ]))
    return rows


def _pulse_texts(story: dict[str, Any], pool: list[dict[str, Any]] | None = None) -> list[str]:
    if pool is None:
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
    return [_plain_from_rich(parts) for parts in _pulse_rich(story, pool)]


def _integer(value: Any) -> int:
    try:
        return int(round(float(value or 0)))
    except (TypeError, ValueError):
        return 0


def _caleb_watch_rich(
    *,
    today_yards: int | None,
    season_yards: int,
    remaining: int,
    pace: int | None,
    is_live: bool,
) -> list[dict[str, str]]:
    parts: list[tuple[Any, str]] = [("🐻 CALEB 4K WATCH 🐻 • ", BEARS_ORANGE)]
    if is_live and today_yards is not None:
        parts.extend([
            ("TODAY: ", WHITE),
            (f"{today_yards:,}", WHITE),
            (" YDS • ", WHITE),
        ])
    parts.extend([
        ("SEASON: ", WHITE),
        (f"{season_yards:,}", WHITE),
        (" YDS • ", WHITE),
        (f"{remaining:,} TO 4K", BEARS_BLUE),
        (" • ", WHITE),
    ])

    if season_yards >= 4000:
        parts.extend([
            ("CALEB WILLIAMS: 4,000+ • ", GOLD),
            ("CHICAGO FINALLY HAS A 4K PASSER 😱", BEARS_ORANGE),
        ])
    elif pace is None:
        parts.extend([
            ("PACE: TBD", WHITE),
            (" • 4K STILL A DREAM", BEARS_ORANGE),
        ])
    elif pace >= 4000:
        parts.extend([
            ("PACE: ", WHITE),
            (f"{pace:,} 👀", GREEN),
            (" • BEARS FANS, DON'T JINX IT", BEARS_ORANGE),
        ])
    else:
        parts.extend([
            ("PACE: ", WHITE),
            (f"{pace:,}", WARNING_ORANGE),
            (" • BEARS HISTORY STILL WAITING...", BEARS_ORANGE),
        ])
    return _rich(parts)


def _caleb_watch_text(*, today_yards: int | None, season_yards: int, remaining: int, pace: int | None, is_live: bool) -> str:
    return _plain_from_rich(_caleb_watch_rich(
        today_yards=today_yards,
        season_yards=season_yards,
        remaining=remaining,
        pace=pace,
        is_live=is_live,
    ))


def build_caleb_4k_watch(
    store,
    week: dict[str, Any],
    *,
    now: datetime | None = None,
    previous: Mapping[str, Any] | None = None,
    nflverse=None,
    espn=None,
) -> dict[str, Any]:
    """Build the tongue-in-cheek Caleb Williams 4,000-yard passing watch.

    The season baseline comes from nflverse once per Pick'em week so Thursday/
    Monday Bears games are not lost. During a Sunday Bears game, today's passing
    yards come from the same ESPN summary surface already trusted for live NFL
    scoring. If either provider is briefly unavailable, callers preserve the
    previous clock snapshot rather than replacing good watch data with zeros.
    """
    from nfl_sources import ESPNProvider, NFLverseProvider, normalize_name, normalize_team
    from weekly import parse_timestamp

    now = (now or datetime.now(UTC)).astimezone(UTC)
    season = int(week.get("season") or 0)
    nfl_week = int(week.get("nfl_week") or 0)
    week_id = str(week.get("id") or "")
    prior = dict(previous or {})

    games = list(store.get_nfl_games(week_id) or [])
    bears_game = next(
        (
            row for row in games
            if "CHI" in {normalize_team(row.get("home_team")), normalize_team(row.get("away_team"))}
        ),
        None,
    )
    status = str((bears_game or {}).get("game_status") or "SCHEDULED").upper()
    kickoff = parse_timestamp((bears_game or {}).get("kickoff_at"))
    is_sunday_game = bool(kickoff and kickoff.astimezone(ET).weekday() == 6)

    baseline_week = _integer(prior.get("baseline_week"))
    baseline_yards = _integer(prior.get("baseline_yards"))
    baseline_games = _integer(prior.get("baseline_games"))
    baseline_ready = baseline_week == nfl_week and nfl_week > 0

    if not baseline_ready:
        if nfl_week <= 1:
            baseline_yards = 0
            baseline_games = 0
        else:
            provider = nflverse or NFLverseProvider()
            rows = provider.weekly_player_stats(season)
            # For an earlier-in-the-week Bears game (Thu/Fri/Sat), include the
            # current-week final row in the Sunday baseline. A Sunday game is
            # kept out of the baseline because ESPN supplies its live yards.
            include_current = bool(bears_game and not is_sunday_game and status == "FINAL")
            max_week = nfl_week if include_current else nfl_week - 1
            matching = []
            for row in rows:
                name = row.get("player_display_name") or row.get("player_name") or ""
                if normalize_name(name) != normalize_name("Caleb Williams"):
                    continue
                row_week = _integer(row.get("week"))
                if row_week <= 0 or row_week > max_week:
                    continue
                matching.append(row)
            if max_week >= 1 and not matching:
                raise RuntimeError("Caleb Williams season baseline is not available yet.")
            baseline_yards = sum(_integer(row.get("passing_yards")) for row in matching)
            baseline_games = len({int(float(row.get("week") or 0)) for row in matching if row.get("week")})
        baseline_week = nfl_week

    today_yards: int | None = None
    today_known = False
    if bears_game and is_sunday_game and status in {"LIVE", "FINAL"} and bears_game.get("provider_event_id"):
        provider = espn or ESPNProvider()
        payload = provider.summary(str(bears_game.get("provider_event_id")))
        entries = provider.player_stats(payload)
        caleb = next(
            (
                row for row in entries
                if normalize_team(row.get("team_abbr")) == "CHI"
                and normalize_name(row.get("player_name")) == normalize_name("Caleb Williams")
            ),
            None,
        )
        if caleb is not None:
            today_yards = _integer((caleb.get("stats") or {}).get("passing_yards"))
            today_known = True
        elif _integer(prior.get("baseline_week")) == nfl_week and prior.get("today_yards") is not None:
            today_yards = _integer(prior.get("today_yards"))
            today_known = True

    # Preserve a previously known live/final Sunday line if ESPN has a brief
    # outage. Provider exceptions are handled by refresh_clock_snapshot; this
    # branch covers a partial response where Caleb's row alone is missing.
    if today_yards is None and is_sunday_game and status in {"LIVE", "FINAL"} and prior.get("today_yards") is not None:
        today_yards = _integer(prior.get("today_yards"))
        today_known = True

    season_yards = baseline_yards + (today_yards or 0)
    games_played = baseline_games + (1 if is_sunday_game and status in {"LIVE", "FINAL"} and today_known else 0)
    pace = int(round((season_yards / games_played) * 17)) if games_played > 0 else None
    remaining = max(0, 4000 - season_yards)
    is_live = bool(is_sunday_game and status == "LIVE")

    return {
        "available": True,
        "player": "Caleb Williams",
        "team": "CHI",
        "baseline_week": nfl_week,
        "baseline_yards": baseline_yards,
        "baseline_games": baseline_games,
        "today_yards": today_yards,
        "season_yards": season_yards,
        "games_played": games_played,
        "remaining": remaining,
        "pace": pace,
        "is_live": is_live,
        "game_status": status,
        "updated_at": now.isoformat(),
        "text": _caleb_watch_text(
            today_yards=today_yards,
            season_yards=season_yards,
            remaining=remaining,
            pace=pace,
            is_live=is_live,
        ),
        "fragments": _caleb_watch_rich(
            today_yards=today_yards,
            season_yards=season_yards,
            remaining=remaining,
            pace=pace,
            is_live=is_live,
        ),
    }


def build_clock_snapshot(store, week: dict[str, Any], *, now: datetime | None = None, caleb_watch: Mapping[str, Any] | None = None) -> dict[str, Any]:
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
    readiness_color = GREEN if registered and confirmed >= registered else WARNING_ORANGE
    readiness_rich = _rich([
        ("SUNDAY PICK'EM • ", TEAL),
        (f"{confirmed}/{registered} LINEUPS READY" if registered else "LINEUPS", readiness_color),
        (" • PICKS LOCK 1 PM ET", WHITE),
    ])

    weekly_rich = _weekly_rich(leaderboard, final=final)
    season_rich = _season_rich(season, int(week.get("nfl_week") or 0))
    live_games_rich = _live_games_rich(list(bundle.get("games") or []))
    player_updates_rich = _player_updates_rich(pool, stats_rows)
    pulses_rich = _pulse_rich(story, pool)

    champions = [row for row in leaderboard if int(row.get("rank") or 0) == 1]
    champion_text = ""
    champion_rich: list[dict[str, str]] = []
    if final and champions:
        names = " + ".join(str(row.get("nickname") or "Player") for row in champions)
        score = float(champions[0].get("score") or 0)
        champion_rich = _rich([
            (f"🏆 WEEK {int(week.get('nfl_week') or 0)} CHAMPION • ", GOLD),
            (names, WHITE),
            (" • ", WHITE),
            (f"{score:.1f} PTS", TEAL),
        ])
        champion_text = _plain_from_rich(champion_rich)

    return {
        "version": CLOCK_SNAPSHOT_VERSION,
        "week_id": week_id,
        "season": int(week.get("season") or 0),
        "nfl_week": int(week.get("nfl_week") or 0),
        "week_label": str(week.get("label") or f"Week {week.get('nfl_week') or ''}"),
        "data_status": str(week.get("data_status") or "WAITING").upper(),
        "generated_at": now.isoformat(),
        "readiness": readiness,
        "readiness_rich": readiness_rich,
        "readiness_all_ready": bool(registered and confirmed >= registered),
        "weekly": _plain_from_rich(weekly_rich),
        "weekly_rich": weekly_rich,
        "season_text": _plain_from_rich(season_rich),
        "season_rich": season_rich,
        "live_games": _live_games_text(list(bundle.get("games") or [])),
        "live_games_rich": live_games_rich,
        "player_updates": [_plain_from_rich(parts) for parts in player_updates_rich],
        "player_updates_rich": player_updates_rich,
        "pulses": [_plain_from_rich(parts) for parts in pulses_rich],
        "pulses_rich": pulses_rich,
        "champion": champion_text,
        "champion_rich": champion_rich,
        "caleb_watch": dict(caleb_watch or {}),
    }


def refresh_clock_snapshot(
    store,
    week: dict[str, Any],
    *,
    refresh_specials: bool = False,
    now: datetime | None = None,
    nflverse=None,
    espn=None,
) -> dict[str, Any] | None:
    """Refresh the server-side clock snapshot if the optional v1.0.7 schema exists."""
    try:
        existing_row = store.get_clock_snapshot(str(week["id"])) if hasattr(store, "get_clock_snapshot") else None
        existing_payload = (existing_row or {}).get("payload") or {}
        existing_watch = existing_payload.get("caleb_watch") or {}
        caleb_watch = existing_watch
        if refresh_specials:
            try:
                caleb_watch = build_caleb_4k_watch(
                    store,
                    week,
                    now=now,
                    previous=existing_watch,
                    nflverse=nflverse,
                    espn=espn,
                )
            except Exception:
                # The joke ticker is optional. Never let a provider hiccup take
                # down the real Pick'em broadcast or erase the last good watch.
                caleb_watch = existing_watch
        payload = build_clock_snapshot(store, week, now=now, caleb_watch=caleb_watch)
        store.upsert_clock_snapshot(str(week["id"]), payload)
        return payload
    except Exception:
        # Clock broadcasting is intentionally optional and may never take the
        # player app or NFL automation down if migration/setup is incomplete.
        return None
