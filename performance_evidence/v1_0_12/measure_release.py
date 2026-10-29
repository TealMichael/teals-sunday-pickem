"""Identical synthetic workloads against a supplied app source tree.

Run each version in its own process. No real database/provider/network access.
Timing covers the actual application refresh, with only I/O replaced by fakes.
"""
import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import socket
import sys
from threading import Lock, get_ident
from time import perf_counter, sleep
from types import SimpleNamespace

parser=argparse.ArgumentParser()
parser.add_argument("source",type=Path)
parser.add_argument("fixtures",type=Path)
parser.add_argument("output",type=Path)
args=parser.parse_args()
sys.path[:0]=[str(args.source.resolve()),str(args.fixtures.resolve())]
blocked=[]
def no_network(*a,**kw):
    blocked.append(True)
    raise AssertionError("External network disabled")
socket.socket.connect=no_network
socket.socket.connect_ex=no_network
socket.create_connection=no_network
socket.getaddrinfo=no_network

import requests
import automation_recovery
import clock_broadcast
import gate4
import gate4_results
import nfl_sources
import nfl_sync
import store as store_module
import weekly
from config import APP_VERSION,APP_BUILD_VERSION
from espn_performance_fixture import Store,WEEK,fixture
from newsletter import build_tuesday_newsletter,perfect_lineup
from personal_season_story import build_personal_season_story
from lineup_reveal import build_lineup_reveal
from pickem_pulse import live_pulse,personal_goal

class FixedDateTime(datetime):
    @classmethod
    def now(cls,tz=None):
        value=cls(2026,10,25,18,2,tzinfo=timezone.utc)
        return value.astimezone(tz) if tz else value.replace(tzinfo=None)
NOW=FixedDateTime.now(timezone.utc)
for module in [store_module,nfl_sync,clock_broadcast,gate4_results,weekly,gate4,automation_recovery]:
    if hasattr(module,"datetime"): module.datetime=FixedDateTime

class MeasuredStore(Store):
    def __init__(self,games,pool):
        super().__init__(games,pool)
        self.cache_events=[]
    def _cache_get(self,key):
        result=super()._cache_get(key)
        self.cache_events.append("hit" if result is not None else "miss")
        return result
    def clear_week_cache(self,week_id=None):
        self.cache_events.append("invalidate")
        return super().clear_week_cache(week_id)

def populated_store(games,pool):
    store=MeasuredStore(games,pool)
    store.tables["weeks"][0].update(published_at="2026-10-20T16:00:00+00:00",is_demo=False,
       opens_at="2026-10-20T16:00:00+00:00",last_data_refresh_at="2026-10-25T17:58:00+00:00")
    store.tables["data_runs"]=[{"id":"state-prior","week_id":WEEK["id"],"run_type":"live_game_state",
       "success":True,"completed_at":NOW.isoformat(),"started_at":NOW.isoformat()}]
    store.tables["players"]=[];store.tables["lineups"]=[];store.tables["lineup_picks"]=[]
    store.tables["weekly_results"]=[]
    for i in range(8):
        player=f"person-{i}"
        store.tables["players"].append({"id":player,"nickname":f"Synthetic {i}","emoji":"🏈"})
        store.tables["lineups"].append({"id":f"lineup-{i}","week_id":WEEK["id"],"player_id":player,
           "confirmed_at":"2026-10-25T16:00:00+00:00" if i<7 else None})
        for position in ["QB","RB","WR","TE","K"] if i<7 else []:
            rank=5 if i==0 and position=="QB" else i%5
            store.tables["lineup_picks"].append({"id":f"pick-{i}-{position}","lineup_id":f"lineup-{i}",
                "position":position,"pool_player_id":f"pool-{rank}-{position}",
                "emergency_pool_player_id":f"pool-6-{position}" if i==0 else None})
        for prior in [6,7]:
            store.tables["weekly_results"].append({"id":f"history-{prior}-{i}","week_id":f"week-{prior}",
               "season":2026,"nfl_week":prior,"player_id":player,"nickname_snapshot":f"Synthetic {i}",
               "emoji_snapshot":"🏈","weekly_score":100-i,"finish_rank":i+1,
               "season_points":gate4.season_points_for_rank(i+1),"is_champion":i==0,
               "finalized_at":"2026-10-19T13:00:00+00:00"})
    return store

class Wire:
    def __init__(self,summaries,games,delay=0.06):
        self.summaries,self.games,self.delay=summaries,games,delay
        self.lock=Lock(); self.active=0; self.peak=0; self.calls=[]; self.waits=[];self.spans=[];self.sessions=[]
    def session(self):
        wire=self
        class Session(requests.Session):
            def __init__(self):
                super().__init__(); self.owner=get_ident();self.closed=False
                with wire.lock: wire.sessions.append(self)
            def get(self,url,params=None,timeout=None):
                assert get_ident()==self.owner
                assert timeout==12
                event=(params or {}).get("gameId") or (params or {}).get("event")
                with wire.lock:
                    wire.active+=1;wire.peak=max(wire.peak,wire.active)
                    wire.calls.append("summary" if event else "scoreboard")
                start=perf_counter()
                try:
                    sleep(wire.delay)
                    if event: payload=wire.summaries[event]
                    else:
                        payload={"events":[{"id":g["provider_event_id"],"date":g["kickoff_at"],
                          "competitions":[{"status":{"period":g["period"],"displayClock":g["game_clock"],
                            "type":{"state":"in","completed":False}},"competitors":[
                            {"homeAway":"home","score":g["home_score"],"team":{"abbreviation":g["home_team"]}},
                            {"homeAway":"away","score":g["away_score"],"team":{"abbreviation":g["away_team"]}}]}]} for g in wire.games]}
                    return SimpleNamespace(raise_for_status=lambda:None,json=lambda:deepcopy(payload))
                finally:
                    stop=perf_counter()
                    with wire.lock:
                        wire.waits.append(stop-start);wire.spans.append((start,stop));wire.active-=1
            def close(self):
                self.closed=True
                super().close()
        return Session()

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def outputs(store):
    week=store.get_week(WEEK["id"])
    bundle=store.get_week_public_bundle(WEEK["id"],fresh=True)
    board=gate4.build_weekly_leaderboard(bundle)
    clock=clock_broadcast.build_clock_snapshot(store,week,now=NOW)
    history=store.get_weekly_results(season=2026)
    final_week={**week,"data_status":"FINAL","finalized_at":NOW.isoformat()}
    archive=gate4_results.archive_week_results(store,final_week)
    results=store.get_weekly_results(season=2026)
    newsletter=build_tuesday_newsletter(final_week=final_week,final_results=archive["rows"],
        perfect=perfect_lineup(bundle["pool"]),season_results=results,next_week={"nfl_week":9},
        lineup_url="https://example.invalid/pickem")
    values={"bundle":bundle,"weekly_board":board,"storylines":gate4.build_storylines(bundle,board),
       "clock":clock,"history_and_final_archive":archive,"season_standings":gate4.build_season_standings(results),
       "achievements":build_personal_season_story(results,"person-0"),"newsletter":newsletter,
       "lineup_reveal":build_lineup_reveal(bundle),
       "pulse":live_pulse(board,"person-0",None,personal_goal(history,"person-0")),
       "saved_picks":deepcopy(store.tables["lineup_picks"]),
       "lock_state":{ "locks_at":week["locks_at"],"locked":NOW>=weekly.parse_timestamp(week["locks_at"])}}
    assert "PHI" in clock["live_games"] and "WAS" in clock["live_games"]
    assert any(not r["is_visible"] for r in bundle["pool"])
    return {k:digest(v) for k,v in values.items()}

def run(kind):
    games,pool,summaries=fixture()
    store=populated_store(games,pool)
    wire=Wire(summaries,games)
    nfl_sources._session=wire.session
    week=deepcopy(store.tables["weeks"][0])
    if kind=="state_only":
        store.tables["weeks"][0]["last_data_refresh_at"]=NOW.isoformat()
        week=deepcopy(store.tables["weeks"][0])
        store.tables["data_runs"][0]["completed_at"]="2026-10-25T17:59:00+00:00"
    elif kind=="lease_busy":
        store.tables["refresh_leases"]=[{"lease_key":f"week:{week['id']}:active-player-stats",
            "owner":"other-synthetic-run","expires_at":"2026-10-25T18:05:00+00:00"}]
    began=perf_counter()
    if kind in {"active","state_only","lease_busy"}:
        updated,info=automation_recovery.maybe_refresh_active_live_lane(store,week,now=NOW)
        if kind!="lease_busy":
            assert info and info["success"]
            assert len(store.tables.get("clock_snapshots",[]))==1, "Clock build failed silently"
    elif kind=="durable":
        info=nfl_sync.refresh_live_scores(store,week)
    else: info=nfl_sync.refresh_live_player_stats(store,week)
    elapsed=perf_counter()-began
    operations=list(store.operations)
    cache=dict(Counter(store.cache_events))
    cold_start=len(store.operations)
    store.get_week_public_bundle(week["id"])
    cold_ops=len(store.operations)-cold_start
    warm_start=len(store.operations)
    warm_begin=perf_counter()
    store.get_week_public_bundle(week["id"])
    warm_seconds=perf_counter()-warm_begin
    warm_ops=len(store.operations)-warm_start
    post_week=deepcopy(store.tables["weeks"][0])
    # Same render's subsequent check must retain existing freshness/lease policy.
    call_count=len(wire.calls); op_count=len(store.operations)
    if kind=="active":
        _,warm_info=automation_recovery.maybe_refresh_active_live_lane(store,post_week,now=NOW)
        assert warm_info is None and len(wire.calls)==call_count
    else: warm_info=None
    repeated_ops=len(store.operations)-op_count
    db_summary={"total":len(operations),"reads":sum(x.endswith(".select") for x in operations),
                "writes":sum(not x.endswith(".select") for x in operations),"by_operation":dict(Counter(operations))}
    # Evidence fixture snapshots are separate from the timed refresh/read counts.
    fingerprint=outputs(store)
    for session in wire.sessions: session.close()
    return {"refresh_seconds":elapsed,"http_wait_sum_seconds":sum(wire.waits),
       "http_span_seconds":max(b for a,b in wire.spans)-min(a for a,b in wire.spans) if wire.spans else 0,
       "http_calls":dict(Counter(wire.calls)),"peak_http_requests":wire.peak,
       "db":db_summary,"cache":cache,"ordinary_bundle_after_refresh_operations":cold_ops,
       "immediate_warm_bundle_operations":warm_ops,"warm_bundle_seconds":warm_seconds,
       "repeat_active_check_operations":repeated_ops,"repeat_active_check_added_http_requests":len(wire.calls)-call_count,
       "lease_outcome":info,"week_score_age_seconds":(NOW-datetime.fromisoformat(post_week["last_data_refresh_at"])).total_seconds(),
       "game_age_seconds":sorted({(NOW-datetime.fromisoformat(g["provider_updated_at"])).total_seconds() for g in store.tables["nfl_games"]}),
       "output_hashes":fingerprint}

result={"version":APP_VERSION,"build":APP_BUILD_VERSION,"python":sys.version,
        "fixture":{"games":10,"pool_rows":45,"hidden_rows":20,"participants":8,"delay_per_http_attempt_s":0.06},
        "scenarios":{name:[run(name) for _ in range(3 if name in {"core","active","durable"} else 1)]
                     for name in ["core","active","durable","state_only","lease_busy"]},
        "blocked_network_attempts":len(blocked)}
assert not blocked
args.output.write_text(json.dumps(result,indent=2)+"\n")
from statistics import median
print(json.dumps({"version":APP_VERSION,"seconds":{k:median(r["refresh_seconds"] for r in v)
 for k,v in result["scenarios"].items()},"queries":{k:v[0]["db"]["total"] for k,v in result["scenarios"].items()}},indent=2))
