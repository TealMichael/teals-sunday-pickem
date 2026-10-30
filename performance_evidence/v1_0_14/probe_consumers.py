"""Fingerprint actual-source public consumers; model only SQL I/O and clock."""
import sys,socket,json,importlib,random
from pathlib import Path
from copy import deepcopy
from time import perf_counter
source,output=map(lambda x:Path(x).resolve(),sys.argv[1:])
sys.path[:0]=[str(source),str(source/'tests')]
blocked=[]
def offline(*a,**k):
    blocked.append(True)
    raise AssertionError('No network allowed')
socket.socket.connect=socket.socket.connect_ex=socket.create_connection=socket.getaddrinfo=offline
from public_bundle_fixture import BenchStore,FixedDateTime,consumer_outputs,WEEK
for name in ['store','weekly','gate4','clock_broadcast','gate4_results','newsletter','personal_season_story','pickem_pulse']:
    setattr(importlib.import_module(name),'datetime',FixedDateTime)
results={}
for count in (0,1,15,50): results[str(count)]=consumer_outputs(BenchStore(count=count))
for shape in ('no_picks','missing_profile'):
    s=BenchStore()
    if shape=='no_picks':s.tables['lineup_picks']=[]
    else:s.tables['players']=s.tables['players'][1:]
    results[shape]=consumer_outputs(s)
for seed in range(30):
    s=BenchStore(count=11);rng=random.Random(seed)
    for table in ['lineups','lineup_picks','players']:rng.shuffle(s.tables[table])
    for row in s.tables['player_pool']:
        if row['id'] in {'pool-0-QB','pool-1-QB'}:row['player_name']='Same Name QB'
    results['ordering_'+str(seed)]=consumer_outputs(s)
timing=[]
for sample in range(3):
    s=BenchStore(delay=.04);start=perf_counter();s.get_week_public_bundle(WEEK['id'])
    timing.append({'seconds':perf_counter()-start,'queries':len(s.requests)})
assert not blocked
output.write_text(json.dumps({'consumer_fingerprints':results,'timing':timing,'blocked_network_attempts':len(blocked)},indent=2)+'\n')
print('PASS',len(results),'consumer scenarios')
