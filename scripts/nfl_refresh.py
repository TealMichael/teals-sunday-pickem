from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import NFL_SEASON
from nfl_sync import (
    ensure_week_shell_from_scoreboard,
    gate3_diagnostic,
    publish_week_pool,
    reconcile_final,
    refresh_injuries,
    refresh_live_scores,
    run_auto,
    sync_schedule,
)
from store import SupabaseStore
from preseason_replay import run_preseason_replay


def _store() -> SupabaseStore:
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = (os.environ.get("SUPABASE_SECRET_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    if not url or not key:
        raise SystemExit("Missing SUPABASE_URL or SUPABASE_SECRET_KEY repository secret.")
    return SupabaseStore(url, key)


def _week(store: SupabaseStore, season: int, week_number: int):
    week = store.get_week_by_season_week(season, week_number)
    if week:
        return week
    return ensure_week_shell_from_scoreboard(store, season=season, nfl_week=week_number)


def _refresh_clock_best_effort(store: SupabaseStore, week=None) -> None:
    try:
        from clock_broadcast import refresh_clock_snapshot
        target = week or store.get_real_week()
        if target:
            target = store.get_week(str(target["id"])) or target
            refresh_clock_snapshot(store, target, refresh_specials=True)
    except Exception:
        pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Teal's Sunday Pick'em Gate 3 NFL refresh")
    parser.add_argument("--mode", choices=["auto", "diagnostic", "preseason_replay", "schedule", "injury", "publish", "live", "final"], default="auto")
    parser.add_argument("--season", type=int, default=NFL_SEASON)
    parser.add_argument("--week", type=int, default=0, help="0 = current real week")
    parser.add_argument("--force", action="store_true", help="Allow manual early publish in an explicit admin/test run.")
    args = parser.parse_args()

    store = _store()
    if args.mode == "auto":
        result = run_auto(store)
        _refresh_clock_best_effort(store)
        print(result)
        return 0
    if args.mode == "preseason_replay":
        print(run_preseason_replay(store))
        return 0

    if args.week:
        week = _week(store, args.season, args.week)
    else:
        base = store.get_real_week()
        if not base:
            base = _week(store, args.season, 1)
        week = store.get_week_by_season_week(int(base["season"]), int(base["nfl_week"])) or base

    result = None
    if args.mode == "diagnostic":
        result = gate3_diagnostic(store, season=int(week["season"]), nfl_week=int(week["nfl_week"]))
    elif args.mode == "schedule":
        result = sync_schedule(store, week)
    elif args.mode == "injury":
        result = refresh_injuries(store, week)
    elif args.mode == "publish":
        result = publish_week_pool(store, week, force=args.force)
    elif args.mode == "live":
        result = refresh_live_scores(store, week)
    elif args.mode == "final":
        result = reconcile_final(store, week)

    if args.mode in {"schedule", "injury", "publish", "live", "final"}:
        _refresh_clock_best_effort(store, week)
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
