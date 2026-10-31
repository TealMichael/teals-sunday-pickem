"""One bounded process-owned worker. Submission never performs network I/O."""
from threading import Lock, Thread
from time import monotonic

class BackgroundRefresh:
    def __init__(self,store):
        self.store=store;self.lock=Lock();self.running=None;self.closed=False
        self.next_submission=0.0;self.last_error_type=None
    def submit(self,week,kind):
        with self.lock:
            if self.closed or self.running is not None or monotonic()<self.next_submission: return False
            self.next_submission=monotonic()+2.0
            thread=Thread(target=self._run,args=(dict(week),kind),name='pickem-refresh',daemon=True)
            self.running=thread
            try: thread.start()
            except Exception:
                self.running=None;self.next_submission=monotonic()+15.0;raise
            return True
    def _run(self,week,kind):
        try:
            from refresh_protocol import execute
            execute(self.store,week,kind);self.last_error_type=None
        except Exception as exc: self.last_error_type=type(exc).__name__
        finally:
            with self.lock: self.running=None
    def close(self):
        with self.lock: self.closed=True

def submit_background(store,week,kind):
    try:
        submitted=store.background_worker().submit(week,kind)
        return week,{'action':kind,'submitted':submitted}
    except Exception as exc:
        return week,{'action':kind,'submitted':False,'error_type':type(exc).__name__}

def live_lane(store,week,kind):
    if week.get('background_enabled') is False:
        try:
            from refresh_protocol import execute
            result=execute(store,week,kind+'_sync')
            return store.read_live_week(str(week['id'])) or week,{'action':kind,'result':result}
        except Exception as exc: return week,{'action':kind,'error_type':type(exc).__name__}
    return submit_background(store,week,kind)
