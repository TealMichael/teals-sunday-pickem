from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, time as dtime, timezone
import time
from typing import Any
from zoneinfo import ZoneInfo

from config import LIVE_SCORE_REFRESH_MINUTES, NFL_SEASON, TIMEZONE_NAME
from nfl_rankings import WEEK1_KICKER_TEAM_ORDER, nflverse_rankings, week1_rankings
from nfl_scoring import score_stat_line
from gate4_results import archive_week_results
from nfl_sources import ESPNProvider, NFLverseProvider, SleeperProvider, normalize_name, normalize_team, parse_iso
from weekly import POSITIONS, parse_timestamp

UTC = timezone.utc
ET = ZoneInfo(TIMEZONE_NAME)
NFL_SYNC_SCHEMA_VERSION = 2


class Gate3Error(RuntimeError):
    pass


def _iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat()


_TRANSIENT_NETWORK_MARKERS = (
    "connection reset",
    "connection aborted",
    "connection refused",
    "remote disconnected",
    "server disconnected",
    "read timed out",
    "connect timeout",
    "read timeout",
    "timed out",
    "temporary failure",
    "temporarily unavailable",
    "bad gateway",
    "service unavailable",
    "gateway timeout",
    "errno 104",
    "errno 54",
)


def _is_transient_network_failure(exc: BaseException) -> bool:
    """Recognize short-lived transport failures worth retrying once in-cycle.

    Provider GETs already have their own HTTP retry adapter. This second layer
    protects the *whole* injury transaction from transient PostgREST/Supabase
    transport resets too, which otherwise leave Saturday data stale until the
    next three-hour GitHub cycle. Logic/database errors are intentionally not
    retried.
    """
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, (ConnectionError, TimeoutError)):
            return True
        name = type(current).__name__.casefold()
        text = str(current).casefold()
        if any(token in name for token in ("connecterror", "readerror", "timeout", "remotedisconnected")):
            return True
        if any(marker in text for marker in _TRANSIENT_NETWORK_MARKERS):
            return True
        current = current.__cause__ or current.__context__
    return False


def sync_schedule(
    store,
    week: dict[str, Any],
    espn: ESPNProvider | None = None,
    nflverse: NFLverseProvider | None = None,
    *,
    prefer_live: bool = False,
) -> list[dict[str, Any]]:
    """Sync one NFL week with nflverse as the schedule/status source."""
    espn = espn or ESPNProvider()
    nflverse = nflverse or NFLverseProvider()
    season = int(week["season"])
    nfl_week = int(week["nfl_week"])
    week_id = str(week["id"])
    games: list[dict[str, Any]] = []
    errors: list[str] = []

    try:
        games = nflverse.schedule_games(season, nfl_week, week_id)
    except Exception as exc:
        errors.append(str(exc))

    # Legacy scoreboard is only an emergency schedule fallback. It is not used
    # for normal live scoring because some cloud providers block site.api.
    if not games:
        try:
            payload = espn.scoreboard(season, nfl_week)
            games = espn.normalize_games(payload, week_id)
        except Exception as exc:
            errors.append(str(exc))

    if not games:
        suffix = f" ({'; '.join(errors[:2])})" if errors else ""
        raise Gate3Error(f"No NFL schedule data was returned for this week{suffix}.")

    if prefer_live and week_id:
        # nflverse is excellent for durable schedule shape but its public file
        # does not carry a live quarter/clock and can temporarily lag a true
        # FINAL. Do not let a schedule/injury sync erase a more precise ESPN
        # state captured by the previous scoring refresh.
        existing = {
            str(row.get("provider_event_id") or ""): row
            for row in store.get_nfl_games(str(week_id))
            if row.get("provider_event_id")
        }
        for game in games:
            prior = existing.get(str(game.get("provider_event_id") or ""))
            if not prior:
                continue
            prior_status = str(prior.get("game_status") or "").upper()
            new_status = str(game.get("game_status") or "").upper()
            preserve = prior_status == "FINAL" or (prior_status == "LIVE" and new_status == "LIVE")
            if preserve:
                for key in ("game_status", "period", "game_clock", "home_score", "away_score", "completed"):
                    if key in prior:
                        game[key] = prior.get(key)
    store.upsert_nfl_games(week_id, games)
    return games


def sync_players(store, sleeper: SleeperProvider | None = None) -> dict[str, list[dict[str, Any]]]:
    sleeper = sleeper or SleeperProvider()
    result: dict[str, list[dict[str, Any]]] = {}
    all_rows: list[dict[str, Any]] = []
    for position in POSITIONS:
        rows = sleeper.active_players(position)
        result[position] = rows
        all_rows.extend(rows)
    store.upsert_nfl_players(all_rows)
    return result


def _eligible_games(games: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [g for g in games if bool(g.get("is_eligible"))]


def _all_positions_exact(ranked: dict[str, list[dict[str, Any]]], count: int = 10) -> bool:
    return all(len(ranked.get(position) or []) == count for position in POSITIONS)


def _team_scoring_order(nflverse: NFLverseProvider, season: int, current_week: int, eligible_teams: set[str]) -> list[str]:
    totals: dict[str, float] = defaultdict(float)
    games_played: dict[str, int] = defaultdict(int)
    for prior_week in range(1, current_week):
        for game in nflverse.schedule_games(season, prior_week):
            if not game.get("completed"):
                continue
            home = normalize_team(game.get("home_team"))
            away = normalize_team(game.get("away_team"))
            if home:
                totals[home] += float(game.get("home_score") or 0)
                games_played[home] += 1
            if away:
                totals[away] += float(game.get("away_score") or 0)
                games_played[away] += 1
    scored = []
    for team in eligible_teams:
        if games_played.get(team):
            scored.append((totals[team] / games_played[team], team))
    scored.sort(reverse=True)
    return [team for _, team in scored]


def build_pool_preview(
    store,
    week: dict[str, Any],
    *,
    espn: ESPNProvider | None = None,
    sleeper: SleeperProvider | None = None,
    nflverse: NFLverseProvider | None = None,
) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    espn = espn or ESPNProvider()
    sleeper = sleeper or SleeperProvider()
    nflverse = nflverse or NFLverseProvider()

    games = sync_schedule(store, week, espn)
    eligible = _eligible_games(games)
    if not eligible:
        raise Gate3Error("No Sunday 1:00 PM ET-or-later games are eligible this week.")
    players = sync_players(store, sleeper)

    nfl_week = int(week["nfl_week"])
    if nfl_week == 1:
        ranked = week1_rankings(players, games)
    else:
        stats = nflverse.weekly_player_stats(int(week["season"]))
        eligible_teams = {normalize_team(g["home_team"]) for g in eligible} | {normalize_team(g["away_team"]) for g in eligible}
        kicker_order = _team_scoring_order(nflverse, int(week["season"]), nfl_week, eligible_teams)
        ranked = nflverse_rankings(
            current_week=nfl_week,
            players_by_position=players,
            games=games,
            stat_rows=stats,
            kicker_team_order=kicker_order,
        )
    if not _all_positions_exact(ranked):
        raise Gate3Error("The weekly ranking did not resolve exactly 10 players at every position.")
    return ranked, games, players


def publish_week_pool(store, week: dict[str, Any], *, force: bool = False) -> dict[str, Any]:
    # Once a real weekly pool is published, the ranked pool is immutable.
    # Injury/schedule handling may promote a hidden replacement through the
    # dedicated replacement paths below, but a retry/manual publish must never
    # re-rank slot 1-10 underneath saved lineups.
    if week.get("published_at"):
        return {"published": False, "message": "Player pool is already published and frozen for this week."}
    now = datetime.now(UTC)
    opens = parse_timestamp(week.get("opens_at"))
    if not force and opens and now < opens:
        return {"published": False, "message": "Not time to publish yet."}
    run_id = store.start_data_run("publish_pool", week_id=str(week["id"]), provider="nflverse+Sleeper")
    try:
        ranked, games, _ = build_pool_preview(store, week)
        store.publish_ranked_pool(week, ranked)
        purged_weeks = store.purge_prior_week_rosters(season=int(week["season"]), before_nfl_week=int(week["nfl_week"]))
        store.finish_data_run(run_id, success=True, message="Published 10 ranked players per position.", metadata={"eligible_games": len(_eligible_games(games)), "purged_roster_weeks": purged_weeks})
        return {"published": True, "message": "Player pool published.", "ranked": ranked}
    except Exception as exc:
        store.update_week_data_state(str(week["id"]), data_status="ERROR", data_message=str(exc))
        store.finish_data_run(run_id, success=False, message=str(exc))
        raise


def _replacement_cutoff(week: dict[str, Any]) -> datetime:
    lock = parse_timestamp(week.get("locks_at"))
    if not lock:
        return datetime.max.replace(tzinfo=UTC)
    sunday = lock.astimezone(ET).date()
    saturday = sunday - timedelta(days=1)
    local = datetime.combine(saturday, dtime(23, 59, 0), tzinfo=ET)
    return local.astimezone(UTC)


def _refresh_injuries_once(store, week: dict[str, Any]) -> dict[str, Any]:
    run_id = store.start_data_run("injury_refresh", week_id=str(week["id"]), provider="Sleeper+nflverse")
    try:
        now = datetime.now(UTC)
        lock = parse_timestamp(week.get("locks_at"))
        # Schedule is refreshed alongside injuries so a late flex/postponement
        # cannot leave an ineligible Monday/early-Sunday player selectable.
        games = sync_schedule(store, week, prefer_live=bool(lock and now >= lock))
        # Pool membership and saved lineup references are frozen at the 1 PM
        # lock. A post-lock schedule feed must never attempt a lineup-pick
        # mutation (the DB correctly rejects those) or destabilize a locked
        # lineup. Live scoring can still observe the updated game schedule.
        before_lock = not lock or now < lock
        schedule_changes = store.reconcile_pool_schedule(week, games) if week.get("published_at") and before_lock else []
        players_by_position = sync_players(store)
        all_players = [p for rows in players_by_position.values() for p in rows]
        changed = store.sync_pool_injury_status(str(week["id"]), all_players, now=now) if week.get("published_at") else []
        replacements: list[dict[str, Any]] = []
        if week.get("published_at") and now <= _replacement_cutoff(week):
            replacements = store.promote_replacements_for_out_players(week)
        # Before lock, this timestamp drives the Sunday Status freshness label.
        # After lock, live scoring owns the shared freshness stamp. Otherwise a
        # successful injury pull could make stale/failed live scores look fresh
        # and suppress the app's scoring-recovery fallback.
        if before_lock:
            store.update_week_data_state(str(week["id"]), last_data_refresh_at=_iso(now))
        store.finish_data_run(
            run_id,
            success=True,
            message=f"NFL status refreshed; {len(changed)} injury changes, {len(replacements)} injury replacements, {len(schedule_changes)} schedule replacements.",
            metadata={"status_changes": len(changed), "replacements": replacements, "schedule_changes": schedule_changes},
        )
        return {"status_changes": changed, "replacements": replacements, "schedule_changes": schedule_changes}
    except Exception as exc:
        store.finish_data_run(run_id, success=False, message=str(exc))
        raise


def refresh_injuries(store, week: dict[str, Any]) -> dict[str, Any]:
    """Refresh schedule/injury data, retrying only transient transport failures.

    A GitHub Saturday cycle is intentionally spaced several hours apart. One
    brief Supabase/provider connection reset should not therefore make the data
    stale for an entire interval. Retry the same idempotent refresh up to two
    additional times with a short backoff; deterministic logic/database errors
    still fail immediately so real bugs stay visible in Diagnostics.
    """
    attempts = 3
    for attempt in range(attempts):
        try:
            return _refresh_injuries_once(store, week)
        except Exception as exc:
            if attempt >= attempts - 1 or not _is_transient_network_failure(exc):
                raise
            time.sleep(0.75 * (2 ** attempt))
    raise RuntimeError("Unreachable injury refresh retry state.")


def _game_by_team(games: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result = {}
    for game in games:
        if not game.get("is_eligible"):
            continue
        result[normalize_team(game.get("home_team"))] = game
        result[normalize_team(game.get("away_team"))] = game
    return result


def refresh_live_scores(store, week: dict[str, Any], espn: ESPNProvider | None = None) -> dict[str, Any]:
    """Refresh live fantasy scores without ever regressing previously captured data.

    nflverse remains the schedule backbone, while each ESPN box-score response
    provides the authoritative live game state (score, quarter/clock, FINAL) for
    the games we are already fetching. Provider failures are isolated per game:
    one bad ESPN response cannot zero or block every other matchup.
    """
    espn = espn or ESPNProvider()
    run_id = store.start_data_run("live_scores", week_id=str(week["id"]), provider="ESPN-CDN+nflverse")
    try:
        games = sync_schedule(store, week, espn, prefer_live=True)
        # Before lock, schedule changes can still remove a now-ineligible game.
        if datetime.now(UTC) < (parse_timestamp(week.get("locks_at")) or datetime.max.replace(tzinfo=UTC)):
            store.reconcile_pool_schedule(week, games)
        eligible = _eligible_games(games)
        pool = store.get_full_week_pool(str(week["id"]))

        # Fetch only games that have started/finalized and still need data. A
        # finalized game whose pool players were already captured as FINAL is
        # intentionally skipped -- and, critically, those players are also
        # skipped later rather than being recalculated from an empty stat line.
        summary_cache: dict[str, list[dict[str, Any]]] = {}
        successful_event_ids: set[str] = set()
        summary_errors: list[dict[str, str]] = []
        merged_games: list[dict[str, Any]] = []
        games_by_event: dict[str, dict[str, Any]] = {
            str(game.get("provider_event_id") or ""): dict(game) for game in eligible if game.get("provider_event_id")
        }
        attempted_summaries = 0

        for game in eligible:
            status = str(game.get("game_status") or "SCHEDULED").upper()
            if status not in {"LIVE", "FINAL"}:
                continue
            game_pool = [
                p for p in pool
                if normalize_team(p.get("team_abbr"))
                in {normalize_team(game.get("home_team")), normalize_team(game.get("away_team"))}
            ]
            if status == "FINAL":
                # A final game with no pool players only matters to the NFL
                # score ticker, whose final score is already stored on nfl_games.
                # Do not keep redownloading its box score for the rest of Sunday.
                if not game_pool:
                    continue
                if all(
                    str(p.get("game_status") or "").upper() == "FINAL" and p.get("score_updated_at")
                    for p in game_pool
                ):
                    continue

            event_id = str(game.get("provider_event_id") or "")
            if not event_id:
                continue
            attempted_summaries += 1
            try:
                summary = espn.summary(event_id)
                entries = espn.player_stats(summary)
                summary_cache[event_id] = entries
                successful_event_ids.add(event_id)

                # The ESPN summary is more timely than nflverse for LIVE/FINAL
                # status and also supplies the quarter/clock used by the Sunday
                # roster/status UI and physical clock.
                merged = dict(game)
                merged.update(ESPNProvider.summary_game_state(summary))
                merged["week_id"] = str(week["id"])
                games_by_event[event_id] = merged
                merged_games.append(merged)
            except Exception as exc:
                # Preserve this game's last known scores and continue updating
                # every other game. Never turn a transient provider miss into a
                # whole-slate outage.
                summary_errors.append({"event_id": event_id, "error_type": type(exc).__name__})

        if attempted_summaries and not successful_event_ids:
            raise Gate3Error("ESPN live summaries were unavailable for all started pool games; previous scores were preserved.")

        if merged_games:
            store.upsert_nfl_games(str(week["id"]), merged_games)

        # Replace the in-memory nflverse rows with any more-accurate ESPN game
        # states before deciding LIVE vs PROVISIONAL and before rendering clocks.
        eligible = [
            games_by_event.get(str(game.get("provider_event_id") or ""), game)
            for game in eligible
        ]
        game_by_team = _game_by_team(eligible)

        normalized_summary: dict[tuple[str, str], dict[str, Any]] = {}
        for entries in summary_cache.values():
            for entry in entries:
                normalized_summary[(normalize_team(entry.get("team_abbr")), normalize_name(entry.get("player_name")))] = entry

        score_rows: list[dict[str, Any]] = []
        preserved_missing_players = 0
        for player in pool:
            game = game_by_team.get(normalize_team(player.get("team_abbr")))
            if not game:
                continue
            game_status = str(game.get("game_status") or "SCHEDULED").upper()
            if game_status == "SCHEDULED":
                continue
            event_id = str(game.get("provider_event_id") or "")
            # Skipped FINAL games and failed ESPN games keep their existing pool
            # score exactly as-is. This prevents a later refresh from replacing
            # a correct final score with 0.0 merely because no summary was loaded.
            if event_id not in successful_event_ids:
                continue

            entry = normalized_summary.get((normalize_team(player.get("team_abbr")), normalize_name(player.get("player_name"))))
            if entry is None and player.get("score_updated_at"):
                preserved_missing_players += 1
                continue

            raw_stats = dict((entry or {}).get("stats") or {})
            result = score_stat_line(raw_stats, str(player.get("position") or ""))
            score_rows.append({
                "pool_player_id": str(player["id"]),
                "source": "espn-live",
                "source_player_id": (entry or {}).get("espn_player_id"),
                "raw_stats": raw_stats,
                "points": result.points,
                "breakdown": result.breakdown,
                "game_status": game_status,
            })

        if score_rows:
            store.upsert_player_week_stats(str(week["id"]), score_rows)

        all_complete = bool(eligible) and all(
            bool(g.get("completed")) or str(g.get("game_status") or "").upper() == "FINAL"
            for g in eligible
        )
        status = "PROVISIONAL" if all_complete else "LIVE"
        if score_rows:
            store.apply_pool_scores(week, score_rows, score_status=status)
        else:
            # A successful refresh can legitimately have no rows to rewrite
            # (for example, every early game is already final). Keep the shared
            # freshness timestamp current without touching any player score.
            store.update_week_data_state(
                str(week["id"]),
                data_status=status,
                last_data_refresh_at=_iso(datetime.now(UTC)),
                data_message="Live NFL refresh completed; existing player scores were preserved.",
            )

        metadata = {
            "eligible_games": len(eligible),
            "summaries": len(summary_cache),
            "summary_errors": summary_errors,
            "preserved_missing_players": preserved_missing_players,
        }
        suffix = f"; {len(summary_errors)} game feed error(s) preserved" if summary_errors else ""
        store.finish_data_run(
            run_id,
            success=True,
            message=f"{status} refresh; {len(score_rows)} pool players updated{suffix}.",
            metadata=metadata,
        )
        return {
            "status": status,
            "players": len(score_rows),
            "games": eligible,
            "summary_errors": summary_errors,
            "preserved_missing_players": preserved_missing_players,
        }
    except Exception as exc:
        store.finish_data_run(run_id, success=False, message=str(exc))
        raise


def _nflverse_row_index(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    index = {}
    for row in rows:
        team = normalize_team(row.get("team") or row.get("recent_team"))
        name = row.get("player_display_name") or row.get("player_name") or ""
        if team and name:
            index[(team, normalize_name(name))] = row
    return index


def reconcile_final(store, week: dict[str, Any], *, nflverse: NFLverseProvider | None = None, espn: ESPNProvider | None = None) -> dict[str, Any]:
    nflverse = nflverse or NFLverseProvider()
    espn = espn or ESPNProvider()
    run_id = store.start_data_run("final_reconcile", week_id=str(week["id"]), provider="nflverse")
    try:
        games = sync_schedule(store, week, espn)
        eligible = _eligible_games(games)
        if not eligible or not all(bool(g.get("completed")) or str(g.get("game_status")) == "FINAL" for g in eligible):
            raise Gate3Error("NFL games are not fully settled yet; finalization was deferred.")

        rows = nflverse.weekly_player_stats(int(week["season"]), int(week["nfl_week"]))
        index = _nflverse_row_index(rows)
        pool = store.get_full_week_pool(str(week["id"]))
        score_rows: list[dict[str, Any]] = []
        preserved_missing = 0
        for player in pool:
            raw = index.get((normalize_team(player.get("team_abbr")), normalize_name(player.get("player_name"))))
            if raw is None and player.get("score_updated_at"):
                # Monday provider rows can occasionally lag or fail name/team
                # resolution for one player. Never replace a verified Sunday
                # ESPN score with 0 solely because the final feed omitted a row.
                preserved_missing += 1
                score_rows.append({
                    "pool_player_id": str(player["id"]),
                    "source": "espn-live-preserved-final",
                    "source_player_id": player.get("espn_player_id"),
                    "raw_stats": {},
                    "points": float(player.get("score_total") or 0),
                    "breakdown": player.get("score_breakdown") or {},
                    "game_status": "FINAL",
                })
                continue
            raw = raw or {}
            result = score_stat_line(raw, str(player.get("position") or ""))
            score_rows.append({
                "pool_player_id": str(player["id"]),
                "source": "nflverse-final",
                "source_player_id": raw.get("player_id") if raw else None,
                "raw_stats": raw,
                "points": result.points,
                "breakdown": result.breakdown,
                "game_status": "FINAL",
            })
        store.upsert_player_week_stats(str(week["id"]), score_rows)
        store.apply_pool_scores(week, score_rows, score_status="FINAL")
        stamp = _iso(datetime.now(UTC))
        finalized_week = store.update_week_data_state(
            str(week["id"]),
            data_status="FINAL",
            finalized_at=stamp,
            last_data_refresh_at=stamp,
            data_message="Monday nflverse reconciliation complete.",
        ) or dict(week, data_status="FINAL", finalized_at=stamp)
        archive = archive_week_results(store, finalized_week)
        store.finish_data_run(
            run_id,
            success=True,
            message=f"Finalized {len(score_rows)} pool players and archived {len(archive.get('rows') or [])} weekly results; preserved {preserved_missing} missing final provider row(s).",
            metadata={"preserved_missing_final_rows": preserved_missing},
        )
        return {
            "finalized": True,
            "players": len(score_rows),
            "results": len(archive.get("rows") or []),
            "preserved_missing_final_rows": preserved_missing,
        }
    except Exception as exc:
        store.finish_data_run(run_id, success=False, message=str(exc))
        raise


def ensure_week_shell_from_scoreboard(
    store,
    *,
    season: int,
    nfl_week: int,
    espn: ESPNProvider | None = None,
    nflverse: NFLverseProvider | None = None,
) -> dict[str, Any]:
    # Function name kept for compatibility; nflverse is now the primary source.
    espn = espn or ESPNProvider()
    nflverse = nflverse or NFLverseProvider()
    existing = store.get_week_by_season_week(season, nfl_week)
    if existing:
        return existing
    games: list[dict[str, Any]] = []
    try:
        games = nflverse.schedule_games(season, nfl_week)
    except Exception:
        payload = espn.scoreboard(season, nfl_week)
        games = espn.normalize_games(payload)
    eligible = _eligible_games(games)
    if not eligible:
        raise Gate3Error(f"Could not find an eligible Sunday for Week {nfl_week}.")
    sunday_dates = sorted({parse_iso(g.get("kickoff_at")).astimezone(ET).date() for g in eligible if parse_iso(g.get("kickoff_at"))})
    if not sunday_dates:
        raise Gate3Error(f"Could not resolve Week {nfl_week} Sunday date.")
    sunday = sunday_dates[0]
    locks_local = datetime.combine(sunday, dtime(13, 0), tzinfo=ET)
    opens_local = datetime.combine(sunday - timedelta(days=5), dtime(12, 0), tzinfo=ET)
    return store.ensure_real_week_shell(
        season=season,
        nfl_week=nfl_week,
        label=f"Week {nfl_week}",
        opens_at=_iso(opens_local),
        locks_at=_iso(locks_local),
    )


def gate3_diagnostic(store, *, season: int = NFL_SEASON, nfl_week: int = 1) -> dict[str, Any]:
    """Real-provider read check. It never publishes the weekly pool.

    Schedule validation uses nflverse first, so an ESPN outage cannot block a
    Tuesday pool build or Commissioner diagnostic.
    """
    week = store.get_week_by_season_week(season, nfl_week)
    if not week:
        week = ensure_week_shell_from_scoreboard(store, season=season, nfl_week=nfl_week)
    run_id = store.start_data_run("diagnostic", week_id=str(week["id"]), provider="ESPN-CDN+Sleeper+nflverse")
    try:
        ranked, games, players = build_pool_preview(store, week)
        result = {
            "week": week,
            "eligible_games": len(_eligible_games(games)),
            "player_counts": {position: len(players.get(position) or []) for position in POSITIONS},
            "ranking_counts": {position: len(ranked.get(position) or []) for position in POSITIONS},
            "visible_preview": {position: [row["player_name"] for row in ranked[position][:5]] for position in POSITIONS},
        }
        store.finish_data_run(run_id, success=True, message="Gate 3 provider diagnostic passed.", metadata=result)
        return result
    except Exception as exc:
        store.finish_data_run(run_id, success=False, message=str(exc))
        raise


def injury_interval_minutes(now_et: datetime) -> int:
    weekday = now_et.weekday()  # Mon 0 ... Sun 6
    if weekday in {1, 2, 3}:  # Tue-Thu
        return 360
    if weekday == 4:  # Friday
        return 240
    if weekday == 5:  # Saturday
        return 180
    if weekday == 6:
        if 8 <= now_et.hour < 11:
            return 60
        if now_et.hour >= 11:
            return 15
        return 180
    return 360


def _run_due(last_run: dict[str, Any] | None, minutes: int, now: datetime) -> bool:
    if not last_run:
        return True
    # Scheduled cadence is measured start-to-start, not completion-to-start.
    # GitHub dispatch/start times still wobble by seconds, so allow a small
    # tolerance rather than requiring a mathematically exact 15:00 interval.
    # Without this, a 1:07:45 start followed by 1:22:20 is only 14:35 apart
    # and would incorrectly skip to 1:37, making Sunday scores look ~30 min old.
    anchor = parse_timestamp(last_run.get("started_at") or last_run.get("completed_at"))
    if not anchor:
        return True
    tolerance = timedelta(seconds=min(90, max(0, int(minutes) * 6)))
    due_after = max(timedelta(0), timedelta(minutes=minutes) - tolerance)
    return (now - anchor) >= due_after


def run_auto(store, *, now: datetime | None = None) -> dict[str, Any]:
    now = (now or datetime.now(UTC)).astimezone(UTC)
    now_et = now.astimezone(ET)
    week = store.get_real_week()
    if not week:
        week = ensure_week_shell_from_scoreboard(store, season=NFL_SEASON, nfl_week=1)
    week = store.get_week_by_season_week(int(week["season"]), int(week["nfl_week"])) or week
    heartbeat_week_id = str(week["id"])
    heartbeat_run_id = store.start_data_run(
        "auto_cycle",
        week_id=heartbeat_week_id,
        provider="github-actions",
        metadata={"build_phase": "gate6"},
    )
    actions: list[str] = []

    def finish_heartbeat(*, success: bool = True, error_type: str | None = None) -> None:
        safe_actions = [str(action).split(":", 1)[0] for action in actions]
        metadata = {"actions": safe_actions, "build_phase": "gate6"}
        if error_type:
            metadata["error_type"] = error_type
        message = "Auto cycle completed" + (f" ({', '.join(safe_actions)})" if safe_actions else " (no action due)")
        store.finish_data_run(heartbeat_run_id, success=success, message=message, metadata=metadata)

    try:
        # Finalization is normally Monday at 9 AM ET, but keep retrying on later
        # runs if nflverse or an official game was not settled at exactly 9:00.
        lock = parse_timestamp(week.get("locks_at"))
        if lock and now >= lock and str(week.get("data_status")) != "FINAL":
            lock_local = lock.astimezone(ET)
            final_local = datetime.combine(lock_local.date() + timedelta(days=1), dtime(9, 0), tzinfo=ET)
            if now >= final_local.astimezone(UTC):
                try:
                    reconcile_final(store, week)
                    actions.append("finalized")
                    next_week_num = int(week["nfl_week"]) + 1
                    if next_week_num <= 18:
                        week = ensure_week_shell_from_scoreboard(store, season=int(week["season"]), nfl_week=next_week_num)
                        week = store.get_week_by_season_week(int(week["season"]), int(week["nfl_week"])) or week
                        actions.append("next_week_shell")
                    else:
                        finish_heartbeat()
                        return {"actions": actions}
                except Exception as exc:
                    actions.append(f"finalize_deferred:{exc}")
                    finish_heartbeat()
                    return {"actions": actions}

        # Tuesday noon: automatically publish only when all 10×5 candidates resolve.
        opens = parse_timestamp(week.get("opens_at"))
        if not week.get("published_at") and opens and now >= opens:
            try:
                publish_week_pool(store, week)
                actions.append("published_pool")
                week = store.get_week_by_season_week(int(week["season"]), int(week["nfl_week"])) or week
            except Exception as exc:
                actions.append(f"publish_failed:{exc}")

        # Injury status ramps up as Sunday approaches. This is a shared backend
        # refresh; user phones never call Sleeper themselves.
        if week.get("published_at"):
            last_injury = store.last_successful_run("injury_refresh", week_id=str(week["id"]))
            if _run_due(last_injury, injury_interval_minutes(now_et), now):
                try:
                    refresh_injuries(store, week)
                    actions.append("injuries")
                except Exception as exc:
                    actions.append(f"injury_failed:{exc}")

        # Sunday 1 PM through roughly 1 AM Monday: live scoring is due every
        # 15 minutes. The workflow itself runs on the same Sunday cadence, while
        # this guard prevents an extra manual auto-cycle from over-fetching.
        scoring_lock = parse_timestamp(week.get("locks_at"))
        if scoring_lock and scoring_lock <= now <= scoring_lock + timedelta(hours=12) and week.get("published_at"):
            last_live = store.last_successful_run("live_scores", week_id=str(week["id"]))
            if _run_due(last_live, LIVE_SCORE_REFRESH_MINUTES, now):
                try:
                    refresh_live_scores(store, week)
                    actions.append("live_scores")
                except Exception as exc:
                    actions.append(f"scores_failed:{exc}")

        finish_heartbeat()
        return {"actions": actions}
    except Exception as exc:
        try:
            finish_heartbeat(success=False, error_type=type(exc).__name__)
        finally:
            raise

