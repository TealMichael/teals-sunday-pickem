"""Compare actual release with untouched v1.0.13, excluding only runtime IDs/build label."""
from pathlib import Path
import json
from statistics import median
ROOT=Path(__file__).resolve().parent
FIELDS=('scenario','ui_tree','buttons','errors','saved_picks','own_picks','mode','position','reactions')
DETAIL={'own_roster_open','own_roster_close','other_roster_open','other_roster_switch'}
def read(name):return json.loads((ROOT/name).read_text())
def writes(record):return {k:v for k,v in record['operations'].items() if not k.endswith('.select')}
checks=[];pairs=[]
for suffix in ['smoke','owner_1','owner_2','owner_3']:
    before,after=read(f'live_baseline_{suffix}.json'),read(f'live_release_{suffix}.json')
    assert before['blocked_network_attempts']==after['blocked_network_attempts']==0
    assert before['delay_per_query_seconds']==after['delay_per_query_seconds']
    assert len(before['results'])==len(after['results'])==17
    for old,new in zip(before['results'],after['results']):
        for field in FIELDS:assert old[field]==new[field],(suffix,old['scenario'],field)
        assert writes(old)==writes(new),(suffix,old['scenario'],'writes')
        if old['scenario'] in DETAIL:assert old['full_runs']==2 and new['full_runs']==1
        else:assert old['full_runs']==new['full_runs']
    checks.append({'pair':'live_'+suffix,'scenarios':17,'outputs_and_writes':'identical'})
    pairs.append((before,after))
timing=[]
for name in ['live_cold_15_players','live_warm','live_expired_cache','own_roster_open','own_roster_close','other_roster_open','other_roster_switch','cheer_add','season_control','after_manual_override','final_results']:
    old=[next(r for r in p[0]['results'] if r['scenario']==name) for p in pairs[1:]]
    new=[next(r for r in p[1]['results'] if r['scenario']==name) for p in pairs[1:]]
    timing.append({'scenario':name,'before_median_seconds':median(r['seconds'] for r in old),'after_median_seconds':median(r['seconds'] for r in new),
        'before_samples':[r['seconds'] for r in old],'after_samples':[r['seconds'] for r in new],
        'before_query_counts':[r['query_count'] for r in old],'after_query_counts':[r['query_count'] for r in new],
        'before_runs':old[0]['full_runs'],'after_runs':new[0]['full_runs']})
for group in ['transitions','due']:
    before,after=[read(f'{group}_{v}.json') for v in ['baseline','release']]
    assert before['blocked_network_attempts']==after['blocked_network_attempts']==0
    assert len(before['results'])==len(after['results'])
    for old,new in zip(before['results'],after['results']):
        for field in FIELDS:assert old[field]==new[field],(group,old['scenario'],field)
        assert writes(old)==writes(new),(group,old['scenario'],'writes')
    checks.append({'pair':group,'scenarios':len(before['results']),'outputs_and_writes':'identical'})
    if group=='due':
        for field in ['provider_calls','provider_peak_concurrency','pool_after_refresh','clock_after_refresh','week_after_refresh']:
            assert before[field]==after[field],field
        assert before['provider_worker_sessions_closed'] and after['provider_worker_sessions_closed']
        due={'before_seconds':before['results'][0]['seconds'],'after_seconds':after['results'][0]['seconds'],
             'before_queries':before['results'][0]['query_count'],'after_queries':after['results'][0]['query_count'],
             'summary_requests':len(before['provider_calls']),'peak_workers':before['provider_peak_concurrency']}
a,b=[read('consumers_'+v+'.json') for v in ['baseline','release']]
assert a['consumer_fingerprints']==b['consumer_fingerprints']
assert a['blocked_network_attempts']==b['blocked_network_attempts']==0
assert len(a['consumer_fingerprints'])==36
assert all(len(v)==12 for v in a['consumer_fingerprints'].values())
bundle={'before_median_seconds':median(r['seconds'] for r in a['timing']),
        'after_median_seconds':median(r['seconds'] for r in b['timing']),
        'before_query_counts':[r['queries'] for r in a['timing']],
        'after_query_counts':[r['queries'] for r in b['timing']]}
assert bundle['before_query_counts']==[5]*3 and bundle['after_query_counts']==[4]*3
result={'status':'PASS','compared_scenario_pairs':sum(c['scenarios'] for c in checks),'checks':checks,
    'consumer_scenario_pairs':36,'consumer_fingerprints_per_scenario':12,'ordering_permutations':30,
    'owner_timing':timing,'cold_bundle_timing':bundle,'due_refresh_sample':due,'network_attempts':0,
    'limits':['Offline synthetic database and provider waiting, not production or iPhone timings.',
        'Whole-app server element trees, not browser pixel screenshots; runtime IDs and build labels normalized.',
        'Profile list order normalized by ID for consumer bundle equality; picks and visible outputs retain exact order.',
        'PostgreSQL joins modeled; actual installed SDK exercised by regression tests using httpx.MockTransport.',
        'Provider refresh still blocks its elected session; cache/refresh schedules unchanged.']}
(ROOT/'comparison.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
