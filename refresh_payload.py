"""Public NFL inputs and a narrow pending result; never a table replacement."""
from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4

GAME_FIELDS = set('provider_event_id home_team away_team kickoff_at is_eligible game_status period game_clock home_score away_score completed over_under spread favored_team provider_updated_at'.split())
STAT_FIELDS = set('pool_player_id source source_player_id raw_stats points breakdown game_status'.split())
WEEK_FIELDS = set('data_status last_data_refresh_at finalized_at data_message'.split())
def stamp(): return datetime.now(timezone.utc).isoformat()

class StagedRefresh:
    _refresh_protocol = False
    _defer_archive = True
    def __init__(self, snapshot):
        self.week = deepcopy(snapshot['week']); self.pool = deepcopy(snapshot['pool']); self.games = deepcopy(snapshot['games'])
        self.lineup_count = snapshot.get('lineup_count',0)
        self.game_updates = {}; self.stat_updates = {}; self.score_updates = {}; self.week_updates = {}; self.runs = {}
        self.score_status = None; self.archive_requested = False
    def _week(self, week_id):
        if str(week_id) != str(self.week['id']): raise ValueError('Refresh cannot cross weeks')
    def get_week(self, week_id):
        self._week(week_id); return deepcopy(self.week)
    def clear_week_cache(self, week_id=None): pass
    def get_nfl_games(self, week_id, *, eligible_only=False):
        self._week(week_id); return deepcopy([g for g in self.games if not eligible_only or g.get('is_eligible')])
    def get_full_week_pool(self, week_id):
        self._week(week_id); return deepcopy(self.pool)
    def upsert_nfl_games(self, week_id, games):
        self._week(week_id); prior = {str(g['provider_event_id']): g for g in self.games}; rows = {}; now=stamp()
        for g in games:
            event=str(g.get('provider_event_id') or '').strip()
            if not event: continue
            row={k:deepcopy(v) for k,v in g.items() if k in GAME_FIELDS}; row['provider_event_id']=event
            old=prior.get(event,{})
            unchanged=old.get('game_status')==row.get('game_status')=='LIVE' and all(old.get(k)==row.get(k) for k in ('period','game_clock','home_score','away_score'))
            row['provider_updated_at']=old.get('provider_updated_at') if unchanged and old.get('provider_updated_at') else now
            rows[event]=row
        for event,row in rows.items():
            self.game_updates[event]=row
            if event in prior: prior[event].update(deepcopy(row))
            else: self.games.append(dict(deepcopy(row),week_id=str(week_id)))
        return [dict(deepcopy(row),week_id=str(week_id)) for row in rows.values()]
    def upsert_player_week_stats(self, week_id, rows):
        self._week(week_id)
        for row in rows: self.stat_updates[str(row['pool_player_id'])]={k:deepcopy(v) for k,v in row.items() if k in STAT_FIELDS}
        return deepcopy(rows)
    def apply_pool_scores(self, week, rows, *, score_status):
        self._week(week['id']); self.score_status=score_status; current={str(p['id']):p for p in self.pool}; output=[]; now=stamp()
        for score in rows:
            player=current.get(str(score['pool_player_id']))
            if not player: continue
            self.score_updates[str(player['id'])]={k:deepcopy(v) for k,v in score.items() if k in STAT_FIELDS}
            player.update(score_total=player.get('manual_score_override') if player.get('manual_score_override') is not None else float(score.get('points') or 0),
                score_status=score_status,score_breakdown=deepcopy(score.get('breakdown') or {}),game_status=score.get('game_status'),
                espn_player_id=score.get('source_player_id') or player.get('espn_player_id'),score_updated_at=now,provider_updated_at=now)
            output.append(deepcopy(player))
        if output: self.update_week_data_state(str(week['id']),data_status=score_status,last_data_refresh_at=now,data_message=f'{score_status.title()} score refresh complete.')
        return output
    def update_week_data_state(self, week_id, **fields):
        self._week(week_id)
        if set(fields)-WEEK_FIELDS: raise ValueError('Unknown staged week field')
        self.week_updates.update(deepcopy(fields)); self.week.update(deepcopy(fields)); return deepcopy(self.week)
    def start_data_run(self, run_type, *, week_id=None, provider=None, metadata=None):
        self._week(week_id); key=str(uuid4())
        self.runs[key]=dict(id=key,run_type=run_type,provider=provider,started_at=stamp(),metadata=deepcopy(metadata or {}),success=None,completed_at=None,message=None)
        return key
    def finish_data_run(self, run_id, *, success, message='', metadata=None):
        self.runs[run_id].update(success=bool(success),completed_at=stamp(),message=str(message))
        if metadata is not None: self.runs[run_id]['metadata']=deepcopy(metadata)
    def payload(self, *, success, preserve_partial=True):
        return dict(version=1,games=list(self.game_updates.values()) if preserve_partial else [],stats=list(self.stat_updates.values()) if preserve_partial else [],
            scores=list(self.score_updates.values()) if preserve_partial else [],score_status=self.score_status if preserve_partial else None,
            week=self.week_updates if preserve_partial else {},runs=list(self.runs.values()),success=bool(success))
