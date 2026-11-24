"""Independent Thanksgiving event. Never writes regular Sunday week or lineup tables.

All mutations use the existing server-only Supabase service role. PostgreSQL
triggers in migration 018 independently enforce event opening, pool membership,
and the Thursday 1 PM ET lock, including cross-device and delayed requests.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from statistics import mean
from typing import Any
from zoneinfo import ZoneInfo

from gate4 import build_weekly_leaderboard, season_points_for_rank
from nfl_scoring import score_stat_line
from nfl_sources import ESPNProvider, NFLverseProvider, SleeperProvider, normalize_name, normalize_team
from weekly import POSITIONS, parse_timestamp

UTC = timezone.utc
ET = ZoneInfo("America/New_York")
TURKEY_BOWL_VERSION = 2
EVENT_TYPE = "turkey_bowl"
EXPECTED_2026 = {frozenset(("CHI", "DET")), frozenset(("PHI", "DAL")), frozenset(("KC", "BUF"))}


class TurkeyBowlError(RuntimeError):
    pass


def is_open(event: dict, now: datetime | None = None) -> bool:
    now = now or datetime.now(UTC)
    opening = parse_timestamp(event.get("opens_at"))
    lock = parse_timestamp(event.get("locks_at"))
    return bool(opening and lock and opening <= now < lock and event.get("published_at"))


def is_locked(event: dict, now: datetime | None = None) -> bool:
    return bool(parse_timestamp(event.get("locks_at")) and (now or datetime.now(UTC)) >= parse_timestamp(event["locks_at"]))


def thanksgiving_games(event: dict, schedule: list[dict]) -> list[dict]:
    """Explicit local DATE filter; never mistake Wednesday/Friday Week 12 for Thursday."""
    date = str(event["game_date"])
    games = [g for g in schedule if parse_timestamp(g.get("kickoff_at"))
             and parse_timestamp(g["kickoff_at"]).astimezone(ET).date().isoformat() == date]
    matchups = {frozenset((normalize_team(g.get("home_team")), normalize_team(g.get("away_team")))) for g in games}
    if len(games) != 3 or len(matchups) != 3 or (
        int(event["season"]) == 2026 and matchups != EXPECTED_2026
    ) or any(not g.get("provider_event_id") for g in games):
        raise TurkeyBowlError("Thanksgiving's three eligible NFL games are not verified; event publication was stopped.")
    return sorted(games, key=lambda g: g["kickoff_at"])


def rank_thanksgiving_pool(players: dict[str, list[dict]], stats: list[dict], games: list[dict], nfl_week: int) -> dict[str, list[dict]]:
    """Five healthy visible choices plus up to five reserves per position.

    The regular Sunday ranker requires TEN kickers, impossible with six holiday
    teams. We use its fantasy scoring formula and historical weekly input, but
    rank ONLY players from Thursday's six teams and keep kicker primaries distinct.
    """
    schedule: dict[str, tuple[str, str]] = {}
    for g in games:
        home, away = normalize_team(g["home_team"]), normalize_team(g["away_team"])
        schedule[home] = (away, str(g["kickoff_at"]))
        schedule[away] = (home, str(g["kickoff_at"]))
    history: dict[tuple[str, str, str], list[tuple[int, float]]] = defaultdict(list)
    for s in stats:
        try:
            week = int(float(s.get("week") or 0))
        except (TypeError, ValueError):
            continue
        if not 1 <= week < nfl_week:
            continue
        pos = str(s.get("position") or "").upper()
        team = normalize_team(s.get("team") or s.get("recent_team"))
        name = normalize_name(s.get("player_display_name") or s.get("player_name") or s.get("player_name_display"))
        if pos in POSITIONS and team and name:
            history[(pos, team, name)].append((week, score_stat_line(s, pos).points))

    result: dict[str, list[dict]] = {}
    for pos in POSITIONS:
        candidates: list[tuple[float, int, str, dict]] = []
        for player in players.get(pos, []):
            team = normalize_team(player.get("team_abbr"))
            if team not in schedule or player.get("active") is False:
                continue
            name = str(player.get("full_name") or "")
            if not name:
                continue
            history_rows = sorted(history.get((pos, team, normalize_name(name)), []))
            values = [v for _, v in history_rows]
            score = mean(values) * .55 + mean(values[-3:]) * .45 if values else -20.0
            depth = int(player.get("depth_order") or 99)
            # QB and K should select starters from the six participating teams.
            # A backup QB's old statistics must not outrank an active starter.
            if pos in {"QB", "K"}:
                score -= max(0, depth - 1) * 30 if depth < 90 else (20 if not values else 0)
            candidates.append((score, depth, name.casefold(), player))
        candidates.sort(key=lambda item: (-item[0], item[1], item[2]))
        unique: list[dict] = []
        seen: set[str] = set()
        seen_kicker_teams: set[str] = set()
        for _, _depth, _name, player in candidates:
            team = normalize_team(player["team_abbr"])
            sid = str(player.get("sleeper_player_id") or f"{team}:{normalize_name(player['full_name'])}")
            if sid in seen or (pos == "K" and team in seen_kicker_teams):
                continue
            seen.add(sid)
            if pos == "K":
                seen_kicker_teams.add(team)
            other, kickoff = schedule[team]
            unique.append({
                "position": pos, "player_name": player["full_name"],
                "sleeper_player_id": player.get("sleeper_player_id"),
                "team_abbr": team, "opponent_abbr": other, "kickoff_at": kickoff,
                "availability_status": player.get("availability_status") or "HEALTHY",
                "raw_injury_status": player.get("injury_status"),
            })
            if len(unique) >= 10:
                break
        # Healthy starters are published first. The reserve slots remain hidden
        # until explicitly promoted for a pre-lock injury.
        healthy = [r for r in unique if r["availability_status"] != "OUT"]
        out = [r for r in unique if r["availability_status"] == "OUT"]
        ordered = healthy + out
        if len(healthy) < 5:
            raise TurkeyBowlError(f"{pos} has only {len(healthy)} healthy Thanksgiving options; publication was stopped.")
        result[pos] = [dict(row, slot_rank=i, is_visible=i <= 5) for i, row in enumerate(ordered, 1)]
    return result


class TurkeyBowlService:
    def __init__(self, store):
        self.store = store

    def table(self, name: str):
        return self.store.client.table(name)

    def event(self, season: int = 2026) -> dict | None:
        rows = (self.table("special_events").select("*")
                .eq("event_type", EVENT_TYPE).eq("season", int(season)).limit(1).execute().data or [])
        return dict(rows[0]) if rows else None

    def events(self) -> list[dict]:
        return list(self.table("special_events").select("*").eq("event_type", EVENT_TYPE).order("season", desc=True).execute().data or [])

    def games(self, event_id: str) -> list[dict]:
        return list(self.table("special_games").select("*").eq("event_id", str(event_id)).order("kickoff_at").execute().data or [])

    def pool(self, event_id: str, *, visible_only: bool = False) -> list[dict]:
        query = self.table("special_pool").select("*").eq("event_id", str(event_id))
        if visible_only:
            query = query.eq("is_visible", True)
        return list(query.order("position").order("slot_rank").execute().data or [])

    def lineup(self, event_id: str, player_id: str) -> tuple[dict | None, list[dict]]:
        rows = (self.table("special_lineups")
                .select("id,event_id,player_id,confirmed_at,updated_at,special_picks(id,lineup_id,position,pool_player_id)")
                .eq("event_id", str(event_id)).eq("player_id", str(player_id)).limit(1).execute().data or [])
        if not rows:
            return None, []
        row = dict(rows[0])
        picks = list(row.pop("special_picks") or [])
        return row, picks

    def save_pick(self, event: dict, player_id: str, pos: str, starter: str) -> None:
        if not is_open(event):
            raise TurkeyBowlError("Turkey Bowl lineup selections are closed.")
        if pos not in POSITIONS:
            raise TurkeyBowlError("Invalid lineup selection.")
        # Always recheck database publication/lock in SQL triggers, not only the UI.
        lineup, _ = self.lineup(str(event["id"]), player_id)
        if not lineup:
            try:
                created = (self.table("special_lineups").insert({
                    "event_id": str(event["id"]), "player_id": str(player_id)
                }).execute().data or [])
                lineup = created[0]
            except Exception:
                lineup, _ = self.lineup(str(event["id"]), player_id)
                if not lineup:
                    raise
        self.table("special_picks").upsert({
            "lineup_id": str(lineup["id"]), "position": pos,
            # Explicitly clear any legacy Thanksgiving backup on edit.
            "pool_player_id": str(starter), "emergency_pool_player_id": None,
        }, on_conflict="lineup_id,position").execute()
        # Re-selecting a starter invalidates the previous 'confirmed' status.
        self.table("special_lineups").update({"confirmed_at": None}).eq("id", str(lineup["id"])).execute()

    def confirm(self, event: dict, player_id: str) -> None:
        if not is_open(event):
            raise TurkeyBowlError("Turkey Bowl lineups have locked.")
        lineup, picks = self.lineup(str(event["id"]), player_id)
        if not lineup or {p["position"] for p in picks} != set(POSITIONS):
            raise TurkeyBowlError("Choose all five positions before confirming.")
        # Thanksgiving is starter-only. QUESTIONABLE/OUT picks are allowed to
        # confirm; if they do not play, they earn their actual (usually zero) points.
        self.table("special_lineups").update({"confirmed_at": datetime.now(UTC).isoformat()}).eq("id", str(lineup["id"])).execute()

    def public_bundle(self, event: dict) -> dict:
        """Must never be called before lock: this contains everybody's private picks."""
        if not is_locked(event):
            raise TurkeyBowlError("Turkey Bowl lineups remain private until Thursday's lock.")
        eid = str(event["id"])
        lineups = list(self.table("special_lineups").select("id,event_id,player_id,confirmed_at").eq("event_id", eid).execute().data or [])
        picks = []
        if lineups:
            picks = list(self.table("special_picks").select("id,lineup_id,position,pool_player_id")
                         .in_("lineup_id", [str(l["id"]) for l in lineups]).execute().data or [])
        profiles = []
        if lineups:
            profiles = list(self.table("players").select("id,nickname,emoji")
                            .in_("id", [str(l["player_id"]) for l in lineups]).execute().data or [])
        # IMPORTANT: Never provide legacy emergency_pool_player_id values to
        # Sunday’s shared scoring helper. That prevents any Thanksgiving
        # substitution without changing Sunday’s scoring contract.
        starter_only_picks = [{k: row.get(k) for k in
                               ("id", "lineup_id", "position", "pool_player_id")}
                              for row in picks]
        return {"lineups": lineups, "picks": starter_only_picks, "players": profiles,
                "pool": self.pool(eid), "games": self.games(eid)}

    def leaderboard(self, event: dict) -> list[dict]:
        return build_weekly_leaderboard(self.public_bundle(event))

    def results(self, *, season: int | None = None) -> list[dict]:
        query = self.table("special_results").select("*")
        if season is not None:
            query = query.eq("season", int(season))
        rows = list(query.order("season", desc=True).order("finish_rank").execute().data or [])
        return [dict(r, is_special_event=True) for r in rows]

    def next_season_champions(self, season: int) -> set[str]:
        """Winner from the previous Thanksgiving wears a badge this season."""
        return {str(r["player_id"]) for r in self.results(season=season - 1) if r.get("is_champion")}

    def sync_schedule(self, event: dict, *, nflverse=None, espn=None) -> list[dict]:
        nflverse = nflverse or NFLverseProvider()
        try:
            schedule = nflverse.schedule_games(int(event["season"]), int(event["nfl_week"]))
            games = thanksgiving_games(event, schedule)
        except Exception:
            espn = espn or ESPNProvider()
            games = thanksgiving_games(event, espn.normalize_games(espn.scoreboard(int(event["season"]), int(event["nfl_week"]))))
        eid = str(event["id"])
        existing = {str(g["provider_event_id"]): g for g in self.games(eid)}
        payload = []
        for game in games:
            prior = existing.get(str(game["provider_event_id"])) or {}
            status = str(game.get("game_status") or "SCHEDULED")
            if prior.get("game_status") == "FINAL" or (prior.get("game_status") == "LIVE" and status == "SCHEDULED"):
                status = prior["game_status"]
            payload.append({
                "event_id": eid, "provider_event_id": str(game["provider_event_id"]),
                "home_team": game["home_team"], "away_team": game["away_team"],
                "kickoff_at": game["kickoff_at"], "game_status": status,
                "completed": status == "FINAL",
                "home_score": game.get("home_score") if status == str(game.get("game_status")) else prior.get("home_score"),
                "away_score": game.get("away_score") if status == str(game.get("game_status")) else prior.get("away_score"),
                "period": game.get("period"), "game_clock": game.get("game_clock"),
                "updated_at": datetime.now(UTC).isoformat(),
            })
        self.table("special_games").upsert(payload, on_conflict="event_id,provider_event_id").execute()
        return self.games(eid)

    def publish(self, event: dict, *, nflverse=None, sleeper=None, espn=None) -> dict:
        if event.get("published_at"):
            return {"published": False, "reason": "already published"}
        if datetime.now(UTC) < parse_timestamp(event["opens_at"]):
            return {"published": False, "reason": "not open"}
        nflverse = nflverse or NFLverseProvider()
        sleeper = sleeper or SleeperProvider()
        games = self.sync_schedule(event, nflverse=nflverse, espn=espn)
        players = {p: sleeper.active_players(p) for p in POSITIONS}
        history = nflverse.weekly_player_stats(int(event["season"]))
        ranked = rank_thanksgiving_pool(players, history, games, int(event["nfl_week"]))
        rows = [dict(r, event_id=str(event["id"])) for p in POSITIONS for r in ranked[p]]
        # All choices are written before publication; never touch them again.
        self.table("special_pool").upsert(rows, on_conflict="event_id,position,slot_rank").execute()
        self.table("special_events").update({"published_at": datetime.now(UTC).isoformat()})\
            .eq("id", str(event["id"])).is_("published_at", "null").execute()
        return {"published": True, "positions": {p: len(ranked[p]) for p in POSITIONS}}

    def refresh_injuries(self, event: dict, *, sleeper=None) -> int:
        if not event.get("published_at") or event.get("finalized_at"):
            return 0
        sleeper = sleeper or SleeperProvider()
        players = {str(r.get("sleeper_player_id")): r
                   for pos in POSITIONS for r in sleeper.active_players(pos) if r.get("sleeper_player_id")}
        now = datetime.now(UTC)
        changes = 0
        eid = str(event["id"])
        for row in self.pool(eid):
            if parse_timestamp(row.get("kickoff_at")) and now >= parse_timestamp(row["kickoff_at"]):
                continue  # Injuries freeze once that player's kickoff passes.
            p = players.get(str(row.get("sleeper_player_id")))
            if not p:
                continue
            status = str(p.get("availability_status") or "HEALTHY")
            if status != row.get("availability_status") or p.get("injury_status") != row.get("raw_injury_status"):
                self.table("special_pool").update({"availability_status": status,
                    "raw_injury_status": p.get("injury_status")}).eq("id", str(row["id"])).execute()
                changes += 1
        # Before lock, promote a healthy hidden reserve into a visible OUT slot.
        if not is_locked(event):
            for pos in POSITIONS:
                pos_rows = [r for r in self.pool(eid) if r["position"] == pos]
                visible_out = [r for r in pos_rows if r["is_visible"] and r["availability_status"] == "OUT"]
                reserves = [r for r in pos_rows if not r["is_visible"] and r["availability_status"] != "OUT"]
                for out, reserve in zip(visible_out, reserves):
                    # The database function swaps both visibility flags atomically;
                    # a worker crash must never leave four or six public choices.
                    self.promote_reserve(event, str(out["id"]), str(reserve["id"]))
                    changes += 1
        return changes

    def refresh_scores(self, event: dict, *, espn=None, nflverse=None) -> dict:
        if not is_locked(event) or not event.get("published_at") or event.get("finalized_at"):
            return {"scored": 0, "reason": "not active"}
        espn = espn or ESPNProvider()
        eid = str(event["id"])
        previous = self.games(eid)
        if len(previous) != 3:
            raise TurkeyBowlError("Three verified Thanksgiving games are required before scoring.")
        # The legacy ESPN site scoreboard can be blocked on cloud runners.
        # Sunday already uses nflverse as its durable schedule authority; keep
        # the same fallback architecture here and use CDN summaries for LIVE
        # quarter/FINAL state and actual fantasy scoring.
        try:
            nflverse = nflverse or NFLverseProvider()
            scoreboard = thanksgiving_games(event, nflverse.schedule_games(int(event["season"]), int(event["nfl_week"])))
        except Exception:
            scoreboard = thanksgiving_games(event, espn.normalize_games(espn.scoreboard(int(event["season"]), int(event["nfl_week"]))))
        by_event = {str(g["provider_event_id"]): g for g in scoreboard}
        pool = self.pool(eid)
        new_games = []
        scored = 0
        errors = []
        for game in previous:
            source = by_event.get(str(game["provider_event_id"]))
            if source is None:
                errors.append(f"Missing ESPN event {game['provider_event_id']}")
                continue
            status = str(source.get("game_status") or "SCHEDULED")
            if game["game_status"] == "FINAL":
                status = "FINAL"  # Never regress a confirmed final game.
            elif game["game_status"] == "LIVE" and status == "SCHEDULED":
                status = "LIVE"
            start = parse_timestamp(game["kickoff_at"])
            if status in {"LIVE", "FINAL"}:
                team_set = {normalize_team(game["home_team"]), normalize_team(game["away_team"])}
                match = [p for p in pool if normalize_team(p["team_abbr"]) in team_set]
                need_box = any(p.get("score_status") != "FINAL" or not p.get("score_updated_at") for p in match)
                if need_box:
                    try:
                        summary = espn.summary(str(game["provider_event_id"]))
                        # CDN summary is more precise than a scoreboard file
                        # that may still report LIVE after the final whistle.
                        summary_status = ESPNProvider.summary_game_state(summary)
                        observed = str(summary_status.get("game_status") or "")
                        if observed == "FINAL" or (observed == "LIVE" and status != "FINAL"):
                            status = observed
                        source = dict(source, **{k: v for k, v in summary_status.items() if v is not None})
                        entries = {(normalize_team(p.get("team_abbr")), normalize_name(p.get("player_name"))): p
                                   for p in espn.player_stats(summary)}
                        # CDN can return a valid game header before the full
                        # stat tables are ready. Never finalize an empty or
                        # wrong-game box score as five zero-point performances.
                        if not entries or not team_set.issubset({team for team, _name in entries}):
                            raise TurkeyBowlError("The Thanksgiving two-team player box score is not ready.")
                        for player in match:
                            entry = entries.get((normalize_team(player["team_abbr"]), normalize_name(player["player_name"])))
                            if entry is None and player.get("score_updated_at"):
                                # ESPN occasionally omits a bench player on a later
                                # replay. Preserve prior points, but record finality
                                # once the complete game boxscore itself succeeds.
                                if status == "FINAL" and player.get("score_status") != "FINAL":
                                    self.table("special_pool").update({"score_status": "FINAL"})\
                                        .eq("id", str(player["id"])).execute()
                                continue
                            if player.get("score_status") == "FINAL" and player.get("score_updated_at"):
                                continue
                            stats = (entry or {}).get("stats") or {}
                            calc = score_stat_line(stats, str(player["position"]))
                            new_status = "FINAL" if status == "FINAL" else "LIVE"
                            if (player.get("score_updated_at") and new_status == player.get("score_status")
                                    and abs(float(player.get("score_total") or 0) - calc.points) < .0005):
                                continue  # Avoid unnecessary writes during unchanged live plays.
                            self.table("special_pool").update({
                                "score_total": calc.points, "score_breakdown": calc.breakdown,
                                "score_status": new_status,
                                "score_updated_at": datetime.now(UTC).isoformat(),
                            }).eq("id", str(player["id"])).execute()
                            scored += 1
                    except Exception as exc:
                        errors.append(f"Box score {game['provider_event_id']}: {type(exc).__name__}")
                        # A failed summary must not let a game be considered final.
                        if status == "FINAL":
                            status = "LIVE"
            new_games.append({
                "event_id": eid, "provider_event_id": str(game["provider_event_id"]),
                "home_team": game["home_team"], "away_team": game["away_team"],
                "kickoff_at": game["kickoff_at"], "game_status": status,
                "completed": status == "FINAL",
                "home_score": source.get("home_score") if source.get("home_score") is not None else game.get("home_score"),
                "away_score": source.get("away_score") if source.get("away_score") is not None else game.get("away_score"),
                "period": source.get("period") or game.get("period"),
                "game_clock": source.get("game_clock") or game.get("game_clock"),
                "updated_at": datetime.now(UTC).isoformat(),
            })
        if new_games:
            self.table("special_games").upsert(new_games, on_conflict="event_id,provider_event_id").execute()
        self.table("special_events").update({"refreshed_at": datetime.now(UTC).isoformat()}).eq("id", eid).execute()
        return {"scored": scored, "game_statuses": [g["game_status"] for g in new_games], "errors": errors}

    def archive(self, event: dict) -> dict:
        """Idempotent full-round awards. Corrections re-upsert same event/player.

        Do not award until the day after Thanksgiving AND all three games are
        confirmed FINAL with complete scoring. Thursday winners stay provisional.
        """
        if not is_locked(event) or not event.get("published_at"):
            raise TurkeyBowlError("Turkey Bowl has not locked.")
        cutoff = parse_timestamp(event["locks_at"]).astimezone(ET) + timedelta(days=1)
        cutoff = cutoff.replace(hour=9, minute=0, second=0, microsecond=0).astimezone(UTC)
        if datetime.now(UTC) < cutoff:
            raise TurkeyBowlError("Turkey Bowl awards finalize Friday at 9 AM ET or later.")
        games = self.games(str(event["id"]))
        if len(games) != 3 or any(g["game_status"] != "FINAL" for g in games):
            raise TurkeyBowlError("All three Thanksgiving games must be FINAL before awarding points.")
        pool = self.pool(str(event["id"]))
        if any(p.get("score_status") != "FINAL" or not p.get("score_updated_at") for p in pool):
            raise TurkeyBowlError("Some Thanksgiving player scores are not FINAL; retry the refresh.")
        leaderboard = self.leaderboard(event)
        stamp = str(event.get("finalized_at") or datetime.now(UTC).isoformat())
        awards = [{
            "event_id": str(event["id"]), "season": int(event["season"]),
            "nfl_week": int(event["nfl_week"]), "player_id": str(row["player_id"]),
            "nickname_snapshot": row["nickname"], "emoji_snapshot": row["emoji"],
            "weekly_score": float(row["score"]), "finish_rank": int(row["rank"]),
            "season_points": season_points_for_rank(int(row["rank"])),
            "is_champion": int(row["rank"]) == 1, "finalized_at": stamp,
        } for row in leaderboard]
        if awards:
            self.table("special_results").upsert(awards, on_conflict="event_id,player_id").execute()
        self.table("special_events").update({"finalized_at": stamp}).eq("id", str(event["id"])).execute()
        return {"players": len(awards), "champions": [r["nickname_snapshot"] for r in awards if r["is_champion"]]}

    def promote_reserve(self, event: dict, outgoing_id: str, incoming_id: str) -> None:
        """One transaction in SQL prevents a brief 4-/6-visible-player pool."""
        if not is_open(event):
            raise TurkeyBowlError("Pool changes are disabled after Thursday's lock.")
        self.store.client.rpc("promote_special_reserve", {
            "p_event_id": str(event["id"]),
            "p_outgoing": str(outgoing_id),
            "p_incoming": str(incoming_id),
        }).execute()

    def correct_score(self, event: dict, pool_id: str, score: float | None, note: str) -> None:
        if not is_locked(event) or not str(note or "").strip() or (score is not None and not -100 <= score <= 250):
            raise TurkeyBowlError("Score corrections require the lock, a reason, and a valid score.")
        found = [r for r in self.pool(str(event["id"])) if str(r["id"]) == str(pool_id)]
        if not found:
            raise TurkeyBowlError("That player is not in this Turkey Bowl.")
        self.table("special_pool").update({"manual_score_override": score, "manual_override_note": note})\
            .eq("id", str(pool_id)).execute()
        if event.get("finalized_at"):
            self.archive(event)  # Recalculate season totals with same unique event/player rows.


def run_auto(store, *, now: datetime | None = None) -> dict:
    """Safe, repeatable holiday worker; no Sunday refresh protocol changes."""
    now = now or datetime.now(UTC)
    service = TurkeyBowlService(store)
    # Only a seeded active season is touched. Other dates and years are no-ops.
    event = service.event(now.astimezone(ET).year)
    if not event:
        return {"status": "no configured Turkey Bowl"}
    opening = parse_timestamp(event["opens_at"])
    lock = parse_timestamp(event["locks_at"])
    if now < opening or now > lock + timedelta(days=5):
        return {"status": "outside event window"}
    if event.get("finalized_at"):
        return {"status": "finalized"}
    if not event.get("published_at"):
        return service.publish(event)
    if now < lock:
        return {"injuries_updated": service.refresh_injuries(event)}
    result = service.refresh_scores(event)
    # Continue updating player availability. No Thanksgiving backups activate.
    try:
        result["injuries_updated"] = service.refresh_injuries(event)
    except Exception as exc:
        result["injury_warning"] = type(exc).__name__
    if not result.get("errors"):
        try:
            result["finalization"] = service.archive(event)
        except TurkeyBowlError:
            pass  # Wait for Friday 9 AM and confirmed final box scores.
    return result
