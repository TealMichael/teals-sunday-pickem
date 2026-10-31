"""Fenced refresh ownership. No Streamlit calls and no shared request context."""
from functools import wraps
from types import SimpleNamespace
from datetime import datetime, timezone

SCORING = {'stats', 'games', 'durable', 'final'}
PROTECTED = {'weeks','nfl_games','player_pool','player_week_stats','weekly_results','season_champions','clock_snapshots'}
class RefreshBusy(RuntimeError): pass
class RefreshExpired(RuntimeError): pass

def native(store): return bool(getattr(store, '_refresh_protocol', False))
def rpc(store, name, **args): return store.client.rpc(name, args).execute().data

def _invalidate(*stores, week_id):
    for store in stores:
        for method,args in (('clear_week_cache',(week_id,)),('_invalidate_real_week_alias',())):
            try: getattr(store,method)(*args)
            except Exception: pass

def coordinated(kind):
    def decorate(fn):
        @wraps(fn)
        def wrapped(store, week, *args, **kwargs):
            if not native(store) or week.get('is_demo') or getattr(store,'_refresh_context',None):
                return fn(store,week,*args,**kwargs)
            def operation(target,current):
                if kind in SCORING and not args and not kwargs.get('espn'):
                    from nfl_sources import ESPNProvider
                    provider=ESPNProvider()
                    try: return fn(target,current,*args,**dict(kwargs,espn=provider))
                    finally:
                        close=getattr(provider.session,'close',None)
                        if close: close()
                return fn(target,current,*args,**kwargs)
            return execute(store,week,kind,operation=operation,force=True)
        return wrapped
    return decorate

def execute(store, week, kind, *, operation=None, force=False):
    """Own a separate transport and acquire ownership before any provider I/O."""
    from refresh_payload import StagedRefresh
    from weekly import parse_timestamp
    owned=store.new_refresh_store();claim=None;committed=False
    try:
        packet=rpc(owned,'refresh_claim',p_week_id=str(week['id']),p_kind=kind,p_force=force)
        if not packet:
            if force: raise RefreshBusy('Another refresh owns this week, or this phase is already complete.')
            return None
        claim=packet['claim'];current=packet['snapshot']['week'];actual=claim['kind']
        owned._refresh_context=claim
        if operation is None:
            import nfl_sync
            names={'stats':'refresh_live_player_stats','games':'refresh_live_game_state','durable':'refresh_live_scores','final':'reconcile_final'}
            fn=getattr(nfl_sync,names[actual])
            def operation(target,current):
                from nfl_sources import ESPNProvider
                provider=ESPNProvider()
                try: return fn(target,current,espn=provider)
                finally:
                    close=getattr(provider.session,'close',None)
                    if close: close()
        lock=parse_timestamp(current.get('locks_at'))
        staged=actual in SCORING and not(actual=='durable' and lock and datetime.now(timezone.utc)<lock)
        if staged:
            stage=StagedRefresh(packet['snapshot']);error=None;result=None
            try:
                from refresh_transport import provider_scope
                with provider_scope(): result=operation(stage,current)
            except Exception as exc: error=exc
            from nfl_sync import Gate3Error
            from nfl_sources import SourceError
            preserve=error is None or isinstance(error,(Gate3Error,SourceError))
            rpc(owned,'refresh_commit',p_claim=claim,p_payload=stage.payload(success=error is None,preserve_partial=preserve))
            committed=True;owned._refresh_context=None
            _invalidate(owned,store,week_id=str(current['id']))
            if error: raise error
            if stage.archive_requested:
                from gate4_results import archive_week_results
                try:
                    archive=archive_week_results(owned,owned.get_week(str(current['id'])))
                    if isinstance(result,dict): result['results']=len(archive.get('rows') or [])
                except Exception:
                    for run_id,run in stage.runs.items():
                        if run['run_type']=='final_reconcile':
                            owned.finish_data_run(run_id,success=False,message='Scores finalized; history archive pending retry.')
                    raise
        else:
            from refresh_transport import provider_scope
            with provider_scope(): result=operation(owned,current)
            if not rpc(owned,'refresh_release',p_claim=claim,p_success=True): raise RefreshExpired('Refresh ownership expired.')
            committed=True;owned._refresh_context=None
            _invalidate(owned,store,week_id=str(current['id']))
        try:
            from clock_broadcast import refresh_clock_snapshot
            refresh_clock_snapshot(owned,owned.get_week(str(current['id'])) or current)
        except Exception: pass
        return result
    finally:
        if claim and not committed:
            try: rpc(owned,'refresh_release',p_claim=claim,p_success=False)
            except Exception: pass
        try: owned.close_refresh_store()
        except Exception: pass

class ProtectedTable:
    def __init__(self,store,name): self.store=store;self.name=name
    def __getattr__(self,key): return getattr(self.store.client.table(self.name),key)
    def insert(self,rows,**kwargs): return ProtectedWrite(self.store,self.name,'insert',rows)
    def upsert(self,rows,*,on_conflict='',**kwargs): return ProtectedWrite(self.store,self.name,'upsert',rows,on_conflict)
    def update(self,row,**kwargs): return ProtectedWrite(self.store,self.name,'update',row)
    def delete(self,**kwargs): return ProtectedWrite(self.store,self.name,'delete',[])

class ProtectedWrite:
    def __init__(self,store,table,operation,rows,conflict=''):
        self.store=store;self.table=table;self.operation=operation
        self.rows=rows if isinstance(rows,list) else [rows];self.conflict=conflict;self.filters=[]
    def eq(self,column,value): self.filters.append(dict(column=column,op='eq',value=value));return self
    def in_(self,column,values): self.filters.append(dict(column=column,op='in',value=values));return self
    def execute(self):
        data=rpc(self.store,'refresh_edit',p_table=self.table,p_operation=self.operation,p_rows=self.rows,p_filters=self.filters,p_conflict=self.conflict,p_claim=getattr(self.store,'_refresh_context',None))
        return SimpleNamespace(data=data or [])

class ArchiveStage:
    _refresh_protocol=False
    def __init__(self,store): self.store=store;self.rows=[];self.champions=[];self.stamp=None
    def __getattr__(self,key): return getattr(self.store,key)
    def upsert_weekly_results(self,rows): self.rows=rows;return rows
    def upsert_season_champions(self,rows): self.champions=rows;return rows
    def update_week_data_state(self,week_id,**fields): self.stamp=fields['results_archived_at']
    def get_weekly_results(self,**kwargs):
        rows=self.store.get_weekly_results(**kwargs);weeks={r['week_id'] for r in self.rows}
        return [r for r in rows if r['week_id'] not in weeks]+self.rows

def archive_current(store,week,build):
    for attempt in range(3):
        revision=rpc(store,'refresh_revision');store.clear_week_cache(str(week['id']))
        store._cache_drop_prefix('weekly_results')
        current=store.get_week(str(week['id'])) or week;stage=ArchiveStage(store)
        result=build(stage,current)
        try:
            rpc(store,'refresh_archive',p_week_id=str(week['id']),p_expected_revision=revision,p_rows=stage.rows,p_champions=stage.champions,p_stamp=stage.stamp)
        except Exception as exc:
            if getattr(exc,'code',None)=='40001' and attempt<2: continue
            raise
        store._cache_drop_prefix('weekly_results');store._cache_drop_prefix('season_champions')
        _invalidate(store,week_id=str(week['id']));return result
