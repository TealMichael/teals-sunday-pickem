from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from io import StringIO
import re
from typing import Any, Iterable
from zoneinfo import ZoneInfo

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import GATE3_HTTP_TIMEOUT_SECONDS, NFL_SEASON_TYPE, TIMEZONE_NAME

UTC = timezone.utc
ET = ZoneInfo(TIMEZONE_NAME)

TEAM_ALIASES = {
    "JAC": "JAX",
    "LA": "LAR",
    "WSH": "WAS",
}


def normalize_team(value: Any) -> str:
    team = str(value or "").strip().upper()
    return TEAM_ALIASES.get(team, team)


def normalize_name(value: Any) -> str:
    text = str(value or "").strip().casefold()
    text = text.replace("’", "'")
    text = re.sub(r"\b(jr|sr|ii|iii|iv)\.?\b", "", text)
    text = re.sub(r"[^a-z0-9]+", "", text)
    return text


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def is_eligible_sunday_kickoff(value: str | datetime | None) -> bool:
    if isinstance(value, datetime):
        dt = value
    else:
        dt = parse_iso(value)
    if not dt:
        return False
    local = dt.astimezone(ET)
    return local.weekday() == 6 and (local.hour, local.minute) >= (13, 0)


def _session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=2,
        connect=2,
        read=2,
        backoff_factor=0.35,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (compatible; TealsSundayPickem/0.3.1; +friends-only-noncommercial)",
        "Accept": "application/json,text/plain,*/*",
    })
    return session


class SourceError(RuntimeError):
    pass


class ESPNProvider:
    SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
    SUMMARY_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary"

    def __init__(self, session: requests.Session | None = None):
        self.session = session or _session()

    def scoreboard(self, season: int, week: int) -> dict[str, Any]:
        """Fetch a weekly scoreboard using two known ESPN query shapes.

        ESPN's site API is undocumented and has accepted both `dates=YYYY` and
        `season=YYYY` over time. Try the more widely documented `dates` form
        first, then the `season` form. Schedule generation does not depend on
        this call anymore; it is primarily a live-status convenience source.
        """
        errors: list[str] = []
        param_sets = (
            {"dates": str(season), "week": week, "seasontype": NFL_SEASON_TYPE},
            {"season": season, "week": week, "seasontype": NFL_SEASON_TYPE},
        )
        for params in param_sets:
            try:
                response = self.session.get(
                    self.SCOREBOARD_URL,
                    params=params,
                    timeout=GATE3_HTTP_TIMEOUT_SECONDS,
                )
                response.raise_for_status()
                payload = response.json()
                if isinstance(payload, dict) and payload.get("events") is not None:
                    return payload
                errors.append("unexpected payload")
            except Exception as exc:
                errors.append(type(exc).__name__)
        detail = ", ".join(errors[:2]) or "unknown error"
        raise SourceError(f"ESPN live scoreboard is temporarily unavailable ({detail}).")

    def summary(self, event_id: str) -> dict[str, Any]:
        try:
            response = self.session.get(
                self.SUMMARY_URL,
                params={"event": event_id},
                timeout=GATE3_HTTP_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            raise SourceError(f"ESPN game {event_id} is temporarily unavailable.") from exc

    @staticmethod
    def normalize_games(payload: dict[str, Any], week_id: str | None = None) -> list[dict[str, Any]]:
        games: list[dict[str, Any]] = []
        for event in payload.get("events") or []:
            competition = (event.get("competitions") or [{}])[0]
            kickoff = event.get("date") or competition.get("date")
            competitors = competition.get("competitors") or []
            home = next((c for c in competitors if c.get("homeAway") == "home"), {})
            away = next((c for c in competitors if c.get("homeAway") == "away"), {})
            home_team = normalize_team((home.get("team") or {}).get("abbreviation"))
            away_team = normalize_team((away.get("team") or {}).get("abbreviation"))
            status = competition.get("status") or event.get("status") or {}
            type_info = status.get("type") or {}
            state = str(type_info.get("state") or "pre").lower()
            completed = bool(type_info.get("completed"))
            status_name = str(type_info.get("name") or "").upper()
            if completed or state == "post":
                game_status = "FINAL"
            elif state == "in":
                game_status = "LIVE"
            elif "POSTPON" in status_name:
                game_status = "POSTPONED"
            elif "CANCEL" in status_name:
                game_status = "CANCELED"
            else:
                game_status = "SCHEDULED"

            odds = (competition.get("odds") or [{}])[0] or {}
            details = str(odds.get("details") or "")
            favored_team = ""
            if details:
                favored_team = normalize_team(details.split()[0])
            games.append({
                "week_id": week_id,
                "provider_event_id": str(event.get("id") or competition.get("id") or ""),
                "home_team": home_team,
                "away_team": away_team,
                "kickoff_at": kickoff,
                "is_eligible": is_eligible_sunday_kickoff(kickoff),
                "game_status": game_status,
                "period": status.get("period"),
                "game_clock": status.get("displayClock"),
                "home_score": _safe_int(home.get("score")),
                "away_score": _safe_int(away.get("score")),
                "completed": completed,
                "over_under": _safe_float(odds.get("overUnder")),
                "spread": _safe_float(odds.get("spread")),
                "favored_team": favored_team or None,
            })
        return [g for g in games if g.get("provider_event_id") and g.get("home_team") and g.get("away_team") and g.get("kickoff_at")]

    @staticmethod
    def player_stats(payload: dict[str, Any]) -> list[dict[str, Any]]:
        """Normalize ESPN summary box-score categories into one stat line/player."""
        merged: dict[tuple[str, str], dict[str, Any]] = {}
        for team_block in ((payload.get("boxscore") or {}).get("players") or []):
            team = normalize_team((team_block.get("team") or {}).get("abbreviation"))
            for category in team_block.get("statistics") or []:
                category_name = str(category.get("name") or category.get("displayName") or "").lower()
                labels = [str(x or "").upper() for x in (category.get("labels") or [])]
                for athlete_row in category.get("athletes") or []:
                    athlete = athlete_row.get("athlete") or {}
                    name = athlete.get("displayName") or athlete.get("shortName") or ""
                    if not name:
                        continue
                    key = (team, normalize_name(name))
                    target = merged.setdefault(key, {
                        "team_abbr": team,
                        "player_name": name,
                        "espn_player_id": str(athlete.get("id") or "") or None,
                        "stats": {},
                    })
                    raw_values = athlete_row.get("stats") or []
                    values = {labels[i]: raw_values[i] for i in range(min(len(labels), len(raw_values)))}
                    _merge_category(target["stats"], category_name, values)
        return list(merged.values())


class SleeperProvider:
    BASE_URL = "https://api.sleeper.app/v1/players/nfl"

    def __init__(self, session: requests.Session | None = None):
        self.session = session or _session()

    def active_players(self, position: str) -> list[dict[str, Any]]:
        try:
            response = self.session.get(
                self.BASE_URL,
                params={"position": position, "active": "true"},
                timeout=GATE3_HTTP_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            raise SourceError(f"Sleeper {position} player data is temporarily unavailable.") from exc

        if isinstance(payload, dict):
            items: Iterable[tuple[str, dict[str, Any]]] = payload.items()
        else:
            items = ((str(row.get("player_id") or ""), row) for row in (payload or []))

        rows: list[dict[str, Any]] = []
        for player_id, p in items:
            pos = str(p.get("position") or "").upper()
            fantasy_positions = {str(x).upper() for x in (p.get("fantasy_positions") or [])}
            if position != pos and position not in fantasy_positions:
                continue
            active = p.get("active") is not False
            if not active:
                continue
            full_name = p.get("full_name") or " ".join(x for x in [p.get("first_name"), p.get("last_name")] if x)
            if not full_name:
                continue
            raw_injury = str(p.get("injury_status") or "").strip()
            rows.append({
                "sleeper_player_id": str(player_id or p.get("player_id") or ""),
                "canonical_key": normalize_name(full_name),
                "full_name": full_name,
                "position": position,
                "team_abbr": normalize_team(p.get("team")),
                "active": True,
                "injury_status": raw_injury or None,
                "availability_status": availability_from_injury(raw_injury),
                "depth_order": _safe_int(p.get("depth_chart_order")),
                "metadata": {
                    "status": p.get("status"),
                    "years_exp": p.get("years_exp"),
                    "number": p.get("number"),
                },
            })
        return rows


class NFLverseProvider:
    PLAYER_STATS_URL = "https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_{season}.csv"
    SCHEDULE_URL = "https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv"

    def __init__(self, session: requests.Session | None = None):
        self.session = session or _session()

    def schedule_games(self, season: int, week: int, week_id: str | None = None) -> list[dict[str, Any]]:
        """Load official-ish nflverse schedule rows for one regular-season week.

        nflverse schedule data updates frequently during the season and exposes
        ESPN event ids, so it is a much better schedule source than making the
        undocumented ESPN site API a hard dependency.
        """
        try:
            response = self.session.get(self.SCHEDULE_URL, timeout=max(GATE3_HTTP_TIMEOUT_SECONDS, 20))
            response.raise_for_status()
        except Exception as exc:
            raise SourceError("nflverse schedule data is temporarily unavailable.") from exc

        rows = csv.DictReader(StringIO(response.text))
        games: list[dict[str, Any]] = []
        now = datetime.now(UTC)
        for row in rows:
            if _safe_int(row.get("season")) != int(season):
                continue
            if str(row.get("game_type") or "").upper() != "REG":
                continue
            if _safe_int(row.get("week")) != int(week):
                continue
            gameday = str(row.get("gameday") or "").strip()
            gametime = str(row.get("gametime") or "").strip()
            if not gameday or not gametime:
                continue
            try:
                kickoff_local = datetime.fromisoformat(f"{gameday}T{gametime}:00").replace(tzinfo=ET)
            except ValueError:
                continue
            kickoff = kickoff_local.astimezone(UTC)
            home_score = _safe_int(row.get("home_score"))
            away_score = _safe_int(row.get("away_score"))
            has_score = home_score is not None and away_score is not None
            completed = bool(has_score and now >= kickoff + timedelta(hours=6))
            if completed:
                game_status = "FINAL"
            elif has_score and now >= kickoff:
                game_status = "LIVE"
            else:
                game_status = "SCHEDULED"

            away_ml = _safe_float(row.get("away_moneyline"))
            home_ml = _safe_float(row.get("home_moneyline"))
            favored_team = None
            if away_ml is not None and home_ml is not None:
                favored_team = normalize_team(row.get("away_team")) if away_ml < home_ml else normalize_team(row.get("home_team"))

            espn_id = str(row.get("espn") or "").strip()
            stable_id = espn_id if espn_id and espn_id.lower() not in {"na", "nan"} else str(row.get("game_id") or "").strip()
            if not stable_id:
                continue
            games.append({
                "week_id": week_id,
                "provider_event_id": stable_id,
                "home_team": normalize_team(row.get("home_team")),
                "away_team": normalize_team(row.get("away_team")),
                "kickoff_at": kickoff.isoformat(),
                "is_eligible": is_eligible_sunday_kickoff(kickoff),
                "game_status": game_status,
                "period": None,
                "game_clock": None,
                "home_score": home_score,
                "away_score": away_score,
                "completed": completed,
                "over_under": _safe_float(row.get("total_line")),
                "spread": _safe_float(row.get("spread_line")),
                "favored_team": favored_team,
            })
        return [g for g in games if g.get("home_team") and g.get("away_team")]

    def weekly_player_stats(self, season: int, week: int | None = None) -> list[dict[str, str]]:
        url = self.PLAYER_STATS_URL.format(season=season)
        try:
            response = self.session.get(url, timeout=max(GATE3_HTTP_TIMEOUT_SECONDS, 20))
            response.raise_for_status()
        except Exception as exc:
            raise SourceError("nflverse player stats are temporarily unavailable.") from exc
        rows = list(csv.DictReader(StringIO(response.text)))
        filtered: list[dict[str, str]] = []
        for row in rows:
            if str(row.get("season_type") or "REG").upper() not in {"REG", "REGULAR"}:
                continue
            if week is not None and _safe_int(row.get("week")) != int(week):
                continue
            row["team"] = normalize_team(row.get("team"))
            filtered.append(row)
        return filtered


def availability_from_injury(raw: str | None) -> str:
    value = str(raw or "").strip().casefold()
    if not value:
        return "HEALTHY"
    if value in {"out", "o", "ir", "pup", "suspended", "reserve", "nfi"} or "injured reserve" in value:
        return "OUT"
    if value in {"questionable", "q", "doubtful", "d", "limited"}:
        return "QUESTIONABLE"
    return "HEALTHY"


def _safe_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int | None:
    number = _safe_float(value)
    return int(number) if number is not None else None


def _fraction_made(value: Any) -> float:
    text = str(value or "").strip()
    if "/" in text:
        text = text.split("/", 1)[0]
    return float(_safe_float(text) or 0)


def _get(values: dict[str, Any], *labels: str) -> float:
    for label in labels:
        if label in values:
            return float(_safe_float(values[label]) or 0)
    return 0.0


def _merge_category(stats: dict[str, float], category: str, values: dict[str, Any]) -> None:
    def add(key: str, value: float) -> None:
        stats[key] = float(stats.get(key, 0.0)) + float(value or 0.0)

    if "passing" in category:
        add("passing_yards", _get(values, "YDS"))
        add("passing_tds", _get(values, "TD", "TDS"))
        add("interceptions", _get(values, "INT"))
        add("passing_2pt_conversions", _get(values, "2PT", "2-PT"))
    elif "rushing" in category:
        add("carries", _get(values, "CAR", "ATT"))
        add("rushing_yards", _get(values, "YDS"))
        add("rushing_tds", _get(values, "TD", "TDS"))
        add("rushing_2pt_conversions", _get(values, "2PT", "2-PT"))
    elif "receiving" in category:
        add("receptions", _get(values, "REC"))
        add("targets", _get(values, "TGTS", "TGT"))
        add("receiving_yards", _get(values, "YDS"))
        add("receiving_tds", _get(values, "TD", "TDS"))
        add("receiving_2pt_conversions", _get(values, "2PT", "2-PT"))
    elif "fumble" in category:
        add("fumbles_lost", _get(values, "LST", "LOST"))
    elif "kickreturn" in category.replace("_", "") or "kick return" in category:
        add("kickoff_return_tds", _get(values, "TD", "TDS"))
    elif "puntreturn" in category.replace("_", "") or "punt return" in category:
        add("punt_return_tds", _get(values, "TD", "TDS"))
    elif "kicking" in category:
        for label in ("FG", "FGM/FGA"):
            if label in values:
                add("field_goals_made", _fraction_made(values[label]))
                break
        for label in ("XP", "XPM/XPA", "PAT"):
            if label in values:
                add("extra_points_made", _fraction_made(values[label]))
                break
