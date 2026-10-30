"""Run paired actual-source AppTest samples sequentially to reduce contention."""
from pathlib import Path
import subprocess,sys
root=Path(__file__).resolve().parent
before,after=map(lambda p:Path(p).resolve(),sys.argv[1:])
for sample in range(1,4):
    for variant,source in [('baseline',before),('release',after)]:
        stem=f'live_{variant}_owner_{sample}'
        with (root/(stem+'.log')).open('w') as out:
            subprocess.run([sys.executable,str(root/'probe_live_bundle.py'),str(source),str(root/(stem+'.json')),
                '--variant',variant,'--owner','--delay','0.04'],stdout=out,stderr=subprocess.STDOUT,check=True)
        print(stem,'PASS',flush=True)
for variant,source in [('baseline',before),('release',after)]:
    stem=f'due_{variant}'
    with (root/(stem+'.log')).open('w') as out:
        subprocess.run([sys.executable,str(root/'probe_due_refresh.py'),str(source),str(root/(stem+'.json')),
            '--variant',variant,'--owner','--delay','0.04'],stdout=out,stderr=subprocess.STDOUT,check=True)
    print(stem,'PASS',flush=True)
