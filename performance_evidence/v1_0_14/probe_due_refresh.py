"""Whole-app live view when this session wins the existing due-refresh lease.

Usage and arguments match probe_live_bundle.py. Uses its anonymous app fixture
plus the previously shipped synthetic ESPN wire fixture. Source stays unchanged.
"""
from pathlib import Path
fixture_source = Path(__file__).with_name('probe_live_bundle.py').read_text().split("measure('live_cold_15_players')", 1)[0]
exec(compile(fixture_source, str(Path(__file__).with_name('probe_live_bundle.py')), 'exec'), globals())

import ast
import requests
import nfl_sources
import clock_broadcast
from threading import Lock
from time import perf_counter, sleep
clock_broadcast.datetime = FixedDateTime

# Reuse only the Wire class, not the historical script's argparse or execution.
wire_path = source / 'performance_evidence/v1_0_12/measure_release.py'
wire_node = next(n for n in ast.parse(wire_path.read_text()).body if isinstance(n, ast.ClassDef) and n.name == 'Wire')
exec(compile(ast.Module(body=[wire_node],type_ignores=[]),str(wire_path),'exec'),globals())
games, pool, summaries = fixture()
wire = Wire(summaries,games,delay=0.06)
nfl_sources._session = wire.session
fs.week['last_data_refresh_at'] = (fixed_now-timedelta(minutes=4)).isoformat()
fs.clear_week_cache()
measure('due_fantasy_refresh')
provider_caller_thread = fs.owner
refresh_calls = list(wire.calls)
assert refresh_calls, 'The due provider refresh was not exercised'
assert len(fs.tables.get('clock_snapshots',[])) == 1, 'Clock snapshot failed silently'
assert fs.week['last_data_refresh_at'] == fixed_now.isoformat()
assert all(s.closed for s in wire.sessions if s.owner != provider_caller_thread), 'Provider worker session was not closed'
pool_after_refresh = deepcopy(fs.tables['player_pool'])
clock_after_refresh = deepcopy(fs.tables['clock_snapshots'])
measure('warm_after_refresh')
assert wire.calls == refresh_calls, 'The immediate warm view repeated provider work'
assert not blocked_attempts
result = {'variant':args.variant,'results':results,'provider_calls':wire.calls,
    'provider_peak_concurrency':wire.peak,'provider_sessions_closed':all(s.closed for s in wire.sessions),
    'provider_worker_sessions_closed':all(s.closed for s in wire.sessions if s.owner != provider_caller_thread),
    'pool_after_refresh':pool_after_refresh,'clock_after_refresh':clock_after_refresh,
    'week_after_refresh':deepcopy(fs.week),'blocked_network_attempts':len(blocked_attempts),
    'database_delay_seconds':args.delay,'provider_delay_seconds':wire.delay,
    'limits':['One paired sample of a successful synchronous refresh; not a production benchmark.',
        'Provider delays are synthetic and PostgreSQL is modeled by the fixture.',
        'The aggregate session flag includes the provider root session; worker cleanup is checked separately.']}
output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
