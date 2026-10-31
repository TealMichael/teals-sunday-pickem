-- v1.0.15. Follow START_HERE_v115.md; starts in compatible synchronous mode.
-- Additive objects in pickem only. Old direct score writers fail closed.
begin;
set local lock_timeout='10s';
create table if not exists pickem.refresh_control (
 singleton boolean primary key default true check(singleton),
 protocol integer not null default 1 check(protocol=1),
 background_enabled boolean not null default false,
 revision bigint not null default 0
);
insert into pickem.refresh_control(singleton) values(true) on conflict do nothing;
create table if not exists pickem.refresh_jobs (
 week_id uuid primary key references pickem.weeks(id) on delete cascade,
 generation bigint not null default 0,input_revision bigint not null default 0,
 owner uuid,kind text,phase text,claimed_at timestamptz,expires_at timestamptz,
 state text not null default 'idle' check(state in ('idle','running','delayed')),
 attempts jsonb not null default '{}',outcomes jsonb not null default '{}',
 archive_pending boolean not null default false
);
alter table pickem.refresh_control enable row level security;
alter table pickem.refresh_jobs enable row level security;
revoke all on pickem.refresh_control,pickem.refresh_jobs from public,anon,authenticated,service_role;

-- One app-specific transaction lock establishes an identical lock order for
-- short writes, including clock/season views. Provider I/O never holds it.
create or replace function pickem.refresh_lock() returns void language sql
set search_path=pg_catalog,pickem,pg_temp as $$ select pg_advisory_xact_lock(115,20261030); $$;

create or replace function pickem.refresh_statement_guard() returns trigger
language plpgsql security definer set search_path=pg_catalog,pickem,pg_temp as $$
begin
 perform pickem.refresh_lock();
 if tg_table_name in ('weeks','nfl_games','player_pool','player_week_stats','weekly_results','season_champions','clock_snapshots') and
 coalesce(current_setting('pickem.refresh_protocol',true),'')<>'1' then
  raise exception 'Refresh protocol required. Complete the v1.0.15 cutover.' using errcode='55000';
 end if;
 return null;
end $$;

create or replace function pickem.refresh_changed() returns trigger
language plpgsql security definer set search_path=pg_catalog,pickem,pg_temp as $$
declare a jsonb;b jsonb;w uuid;protected boolean:=false;
begin
 a:=case when tg_op='INSERT' then '{}'::jsonb else to_jsonb(old) end;
 b:=case when tg_op='DELETE' then '{}'::jsonb else to_jsonb(new) end;
 if tg_table_name='players' and tg_op='UPDATE' and (a->'nickname',a->'emoji') is not distinct from (b->'nickname',b->'emoji') then return null;end if;
 update pickem.refresh_control set revision=revision+1 where singleton;
 if tg_table_name='weeks' then
  w:=coalesce((b->>'id')::uuid,(a->>'id')::uuid);
  protected:=tg_op<>'UPDATE' or (a->'locks_at',a->'published_at',a->'data_status',a->'season',a->'nfl_week',a->'is_demo') is distinct from (b->'locks_at',b->'published_at',b->'data_status',b->'season',b->'nfl_week',b->'is_demo');
 elsif tg_table_name='player_pool' then
  w:=coalesce((b->>'week_id')::uuid,(a->>'week_id')::uuid);
  protected:=tg_op<>'UPDATE' or (a-array['score_total','score_status','score_breakdown','game_status','score_updated_at','provider_updated_at','manual_score_override','manual_override_at','manual_override_note']) is distinct from (b-array['score_total','score_status','score_breakdown','game_status','score_updated_at','provider_updated_at','manual_score_override','manual_override_at','manual_override_note']);
 elsif tg_table_name='nfl_games' then
  w:=coalesce((b->>'week_id')::uuid,(a->>'week_id')::uuid);protected:=true;
 end if;
 if protected and exists(select 1 from pickem.weeks where id=w) and coalesce(current_setting('pickem.refresh_week',true),'')<>w::text then
  insert into pickem.refresh_jobs(week_id) values(w) on conflict do nothing;
  update pickem.refresh_jobs set input_revision=input_revision+1,generation=generation+1,owner=null,expires_at=null,state='idle' where week_id=w;
 end if;
 return null;
end $$;

do $$ declare t text;begin
 foreach t in array array['weeks','nfl_games','player_pool','player_week_stats','weekly_results','season_champions','clock_snapshots','lineups','lineup_picks','players'] loop
  execute format('drop trigger if exists refresh_lock_before on pickem.%I',t);
  execute format('create trigger refresh_lock_before before insert or update or delete or truncate on pickem.%I for each statement execute function pickem.refresh_statement_guard()',t);
  if t<>'clock_snapshots' then
   execute format('drop trigger if exists refresh_revision_after on pickem.%I',t);
   execute format('create trigger refresh_revision_after after insert or update or delete on pickem.%I for each row execute function pickem.refresh_changed()',t);
  end if;
 end loop;
end $$;

create or replace function pickem.refresh_assert(p_claim jsonb) returns pickem.refresh_jobs
language plpgsql security definer set search_path=pg_catalog,pickem,pg_temp as $$
declare j pickem.refresh_jobs;
begin
 perform pickem.refresh_lock();select * into j from pickem.refresh_jobs where week_id=(p_claim->>'week_id')::uuid for update;
 if j.owner is null or j.owner is distinct from (p_claim->>'owner')::uuid or j.generation is distinct from (p_claim->>'generation')::bigint or j.input_revision is distinct from (p_claim->>'input_revision')::bigint or j.expires_at<=clock_timestamp() then
  raise exception 'Refresh ownership expired or changed' using errcode='40001';
 end if;return j;
end $$;

create or replace function pickem.refresh_claim(p_week_id uuid,p_kind text,p_force boolean default false) returns jsonb
language plpgsql security definer set search_path=pg_catalog,pickem,pg_temp as $$
declare j pickem.refresh_jobs;w pickem.weeks;n timestamptz;last_game timestamptz;last_score timestamptz;ttl integer;enabled boolean;
 k text:=case when p_kind='active_sync' then 'active' when p_kind='recovery_sync' then 'recovery' else p_kind end;
 stat_attempt timestamptz;game_attempt timestamptz;durable_attempt timestamptz;
begin
 perform pickem.refresh_lock();n:=clock_timestamp();select * into w from pickem.weeks where id=p_week_id;
 if not found or w.is_demo then return null;end if;
 if k is null or k not in ('active','recovery','stats','games','durable','final','injury','schedule','publish') then raise exception 'Unknown refresh kind';end if;
 select background_enabled into enabled from pickem.refresh_control where singleton;
 if k in ('active','recovery') and not enabled and p_kind not in ('active_sync','recovery_sync') then return null;end if;
 insert into pickem.refresh_jobs(week_id) values(p_week_id) on conflict do nothing;
 select * into j from pickem.refresh_jobs where week_id=p_week_id for update;
 if j.owner is not null and j.expires_at>n and not(k='final' and j.kind in ('stats','games','durable')) then return null;end if;
 if k in ('active','recovery') and (w.published_at is null or n<w.locks_at or n>w.locks_at+interval '12 hours' or w.data_status='FINAL') then return null;end if;
 if k='active' and w.data_status='PROVISIONAL' then return null;end if;
 if k in ('stats','games','durable') and w.data_status='FINAL' then return null;end if;
 select max(coalesce(completed_at,started_at)) into last_game from pickem.data_runs where week_id=p_week_id and run_type='live_game_state' and success;
 select greatest((j.attempts->>'stats')::timestamptz,max(coalesce(completed_at,started_at))) into stat_attempt from pickem.data_runs where week_id=p_week_id and run_type='live_player_stats';
 select greatest((j.attempts->>'games')::timestamptz,max(coalesce(completed_at,started_at))) into game_attempt from pickem.data_runs where week_id=p_week_id and run_type='live_game_state';
 select greatest((j.attempts->>'durable')::timestamptz,max(coalesce(completed_at,started_at))) into durable_attempt from pickem.data_runs where week_id=p_week_id and run_type='live_scores';
 if k='active' then
  if (last_game is null or last_game<=n-interval '2 minutes') and j.kind='stats' and coalesce(game_attempt,'-infinity')<=n-interval '1 minute' then k:='games';
  elsif (w.last_data_refresh_at is null or w.last_data_refresh_at<=n-interval '3 minutes') and coalesce(stat_attempt,'-infinity')<=n-interval '2 minutes' then k:='stats';
  elsif (last_game is null or last_game<=n-interval '2 minutes') and coalesce(game_attempt,'-infinity')<=n-interval '1 minute' then k:='games';
  else return null;end if;
 elsif k='recovery' then
  if w.data_status not in ('LIVE','PROVISIONAL') and n<w.locks_at+interval '10 minutes' then return null;end if;
  if w.data_status in ('LIVE','PROVISIONAL') and w.last_data_refresh_at>n-interval '7 minutes' then return null;end if;
  select max(coalesce(completed_at,started_at)) into last_score from pickem.data_runs where week_id=p_week_id and run_type='live_scores' and success;
  if last_score>n-interval '7 minutes' or durable_attempt>n-interval '5 minutes' then return null;end if;k:='durable';
 elsif k='durable' and not p_force then
  -- Match nfl_sync._run_due: five minutes start-to-start with its existing
  -- 30-second dispatch tolerance. Completion time must not skip a due job.
  select max(coalesce(started_at,completed_at)) into last_score from pickem.data_runs where week_id=p_week_id and run_type='live_scores' and success;
  if last_score>n-interval '270 seconds' then return null;end if;
 end if;
 ttl:=case when k in ('stats','games','durable') then 240 else 420 end;
 update pickem.refresh_jobs set generation=generation+1,owner=gen_random_uuid(),kind=k,phase=w.data_status,claimed_at=n,expires_at=n+make_interval(secs=>ttl),state='running',attempts=attempts||jsonb_build_object(k,n) where week_id=p_week_id returning * into j;
 return jsonb_build_object('claim',jsonb_build_object('week_id',p_week_id,'owner',j.owner,'generation',j.generation,'input_revision',j.input_revision,'kind',k,'expires_at',j.expires_at,'seconds',ttl),
  'snapshot',jsonb_build_object('week',to_jsonb(w),'pool',coalesce((select jsonb_agg(to_jsonb(p) order by p.position,p.slot_rank) from pickem.player_pool p where week_id=p_week_id),'[]'::jsonb),
  'games',coalesce((select jsonb_agg(to_jsonb(g) order by g.kickoff_at) from pickem.nfl_games g where week_id=p_week_id),'[]'::jsonb),'lineup_count',(select count(*) from pickem.lineups where week_id=p_week_id)));
end $$;

create or replace function pickem.refresh_release(p_claim jsonb,p_success boolean) returns boolean
language plpgsql security definer set search_path=pg_catalog,pickem,pg_temp as $$
declare j pickem.refresh_jobs;
begin
 perform pickem.refresh_lock();select * into j from pickem.refresh_jobs where week_id=(p_claim->>'week_id')::uuid for update;
 if j.owner is null or j.owner is distinct from (p_claim->>'owner')::uuid or j.generation is distinct from (p_claim->>'generation')::bigint or j.expires_at<=clock_timestamp() then return false;end if;
 update pickem.refresh_jobs set owner=null,expires_at=null,state=case when p_success then 'idle' else 'delayed' end,outcomes=outcomes||jsonb_build_object(j.kind,jsonb_build_object('success',p_success,'at',clock_timestamp())) where week_id=j.week_id;
 return true;
end $$;

create or replace function pickem.refresh_read_week(p_week_id uuid) returns jsonb
language sql stable security definer set search_path=pg_catalog,pickem,pg_temp as $$
 select to_jsonb(w)||jsonb_build_object('refresh_status',case
 when j.owner is not null and j.expires_at>statement_timestamp() then 'running'
 when j.state='delayed' or (j.owner is not null and j.expires_at<=statement_timestamp()) or
 exists(select 1 from jsonb_each(j.outcomes) o where o.key in ('stats','durable') and (o.value->>'success')::boolean=false and (o.value->>'at')::timestamptz>coalesce(w.last_data_refresh_at,'-infinity')) then 'delayed'
 else 'idle' end,'refresh_revision',c.revision,'background_enabled',c.background_enabled,'archive_pending',coalesce(j.archive_pending,false))
 from pickem.weeks w cross join pickem.refresh_control c left join pickem.refresh_jobs j on j.week_id=w.id where w.id=p_week_id;
$$;
create or replace function pickem.refresh_revision() returns bigint language sql stable security definer set search_path=pg_catalog,pickem,pg_temp as $$ select revision from pickem.refresh_control where singleton; $$;
create or replace function pickem.refresh_pending_archives() returns jsonb
language sql stable security definer set search_path=pg_catalog,pickem,pg_temp as $$
 select coalesce(jsonb_agg(to_jsonb(w) order by w.season,w.nfl_week),'[]'::jsonb)
 from pickem.weeks w join pickem.refresh_jobs j on j.week_id=w.id where j.archive_pending and w.data_status='FINAL';
$$;
create or replace function pickem.refresh_set_background(p_enabled boolean) returns jsonb
language plpgsql security definer set search_path=pg_catalog,pickem,pg_temp as $$
begin
 perform pickem.refresh_lock();update pickem.refresh_control set background_enabled=p_enabled where singleton;
 if not p_enabled then update pickem.refresh_jobs set generation=generation+1,owner=null,expires_at=null,state='idle';end if;
 return jsonb_build_object('protocol',1,'background_enabled',p_enabled);
end $$;

-- Finite table/column operations for existing commissioner and scheduler paths.
-- Values are typed through the real table row type, never executable input.
create or replace function pickem.refresh_edit(p_table text,p_operation text,p_rows jsonb default '[]',p_filters jsonb default '[]',p_conflict text default '',p_claim jsonb default null,p_expected_revision bigint default null) returns jsonb
language plpgsql security definer set search_path=pg_catalog,pickem,pg_temp as $$
declare allowed text[];r jsonb;f jsonb;keys text[];cols text;vals text;sets text;pred text:='true';q text;got jsonb;outrows jsonb:='[]';w uuid;demo boolean;j pickem.refresh_jobs;conf text;item jsonb;
begin
 perform pickem.refresh_lock();
 if p_claim is not null then j:=pickem.refresh_assert(p_claim);perform set_config('pickem.refresh_week',j.week_id::text,true);end if;
 allowed:=case p_table
 when 'weeks' then string_to_array('id,season,nfl_week,label,opens_at,locks_at,published_at,is_demo,created_at,data_status,last_data_refresh_at,finalized_at,data_message,results_archived_at,rosters_purged_at',',')
 when 'nfl_games' then string_to_array('id,week_id,provider_event_id,home_team,away_team,kickoff_at,is_eligible,game_status,period,game_clock,home_score,away_score,completed,over_under,spread,favored_team,provider_updated_at',',')
 when 'player_pool' then string_to_array('id,week_id,position,slot_rank,player_name,nfl_player_id,team_abbr,opponent_abbr,kickoff_at,is_visible,availability_status,created_at,sleeper_player_id,espn_player_id,raw_injury_status,schedule_eligible,schedule_note,score_total,score_status,score_breakdown,game_status,score_updated_at,manual_score_override,manual_override_at,manual_override_note,provider_updated_at',',')
 when 'player_week_stats' then string_to_array('id,week_id,pool_player_id,source,source_player_id,raw_stats,points,breakdown,game_status,updated_at',',')
 when 'lineup_picks' then string_to_array('id,lineup_id,emergency_pool_player_id,updated_at',',')
 when 'weekly_results' then string_to_array('id,week_id,season,nfl_week,player_id,nickname_snapshot,emoji_snapshot,weekly_score,finish_rank,season_points,is_champion,finalized_at',',')
 when 'season_champions' then string_to_array('id,season,player_id,nickname_snapshot,emoji_snapshot,season_points,total_fantasy_points,awarded_at',',')
 when 'clock_snapshots' then array['week_id','payload','updated_at'] end;
 if allowed is null or p_operation not in ('insert','upsert','update','delete') or jsonb_typeof(p_rows) is distinct from 'array' or jsonb_typeof(p_filters) is distinct from 'array' then raise exception 'Invalid refresh edit';end if;
 if p_table in ('weekly_results','season_champions','clock_snapshots') and p_expected_revision is distinct from pickem.refresh_revision() then raise exception 'Derived input changed' using errcode='40001';end if;
 if p_table='lineup_picks' and (p_claim is null or p_operation<>'update') then raise exception 'Invalid backup edit';end if;
 if p_operation='delete' and p_table<>'player_week_stats' then raise exception 'Unsupported delete';end if;
 if p_operation in ('update','delete') and jsonb_array_length(p_filters)=0 then raise exception 'A targeted filter is required';end if;
 if p_operation='update' and jsonb_array_length(p_rows)<>1 then raise exception 'One update row required';end if;
 for f in select value from jsonb_array_elements(p_filters) loop
  if not (f->>'column'=any(allowed)) or f->>'op' not in ('eq','in') then raise exception 'Invalid filter';end if;
  if f->>'op'='eq' then pred:=pred||format(' and %I::text=%L',f->>'column',f->>'value');
  else
   if jsonb_typeof(f->'value') is distinct from 'array' then raise exception 'Invalid filter values';end if;
   pred:=pred||format(' and %I::text in (select jsonb_array_elements_text(%L::jsonb))',f->>'column',(f->'value')::text);
  end if;
 end loop;
 perform set_config('pickem.refresh_protocol','1',true);
 for r in select value from jsonb_array_elements(case when p_operation='delete' then '[{}]'::jsonb else p_rows end) loop
  if jsonb_typeof(r) is distinct from 'object' then raise exception 'Object required';end if;
  select array_agg(key order by key) into keys from jsonb_object_keys(r) key;
  if not coalesce(keys<@allowed,true) then raise exception 'Unknown edit column';end if;
  if p_operation='update' and r ?| array['id','week_id','lineup_id'] then raise exception 'Identity update forbidden';end if;
  select string_agg(format('%I',k),','),string_agg(format('v.%I',k),','),string_agg(format('%I=v.%I',k,k),',') into cols,vals,sets from unnest(keys) k;
  if p_operation in ('insert','upsert') then
   q:=format('insert into pickem.%I (%s) select %s from jsonb_populate_record(null::pickem.%I,$1) v',p_table,cols,vals,p_table);
   if p_operation='upsert' then
    conf:=case p_table when 'weeks' then 'season,nfl_week,is_demo' when 'nfl_games' then 'week_id,provider_event_id' when 'player_pool' then 'week_id,position,slot_rank' when 'player_week_stats' then 'week_id,pool_player_id' when 'weekly_results' then 'week_id,player_id' when 'season_champions' then 'season,player_id' when 'clock_snapshots' then 'week_id' end;
    if p_conflict='id' and r?'id' then conf:='id';elsif p_conflict<>conf then raise exception 'Invalid conflict key';end if;
    select string_agg(format('%I=excluded.%I',k,k),',') into sets from unnest(keys) k;
    q:=q||format(' on conflict (%s) do update set %s',conf,sets);
   end if;
  elsif p_operation='update' then q:=format('update pickem.%I t set %s from jsonb_populate_record(null::pickem.%I,$1) v where %s',p_table,sets,p_table,replace(pred,' and ',' and t.'));
  else q:=format('delete from pickem.%I where %s',p_table,pred);end if;
  q:='with changed as ('||q||' returning '||case when p_operation='update' then 't.*' else '*' end||') select coalesce(jsonb_agg(to_jsonb(changed)),''[]''::jsonb) from changed';
  execute q into got using r;
  for item in select value from jsonb_array_elements(got) loop
   w:=case when p_table='weeks' then (item->>'id')::uuid when p_table='lineup_picks' then (select week_id from pickem.lineups where id=(item->>'lineup_id')::uuid) else (item->>'week_id')::uuid end;
   if p_claim is not null and w is not null and w<>j.week_id then raise exception 'Cross-week mutation forbidden';end if;
   select is_demo into demo from pickem.weeks where id=w;
   if p_claim is null and not coalesce(demo,false) then
    if p_table in ('nfl_games','player_week_stats') or (p_table='player_pool' and r ?| array['score_total','score_status','score_breakdown','score_updated_at','manual_score_override','manual_override_at','manual_override_note']) or
       (p_table='weeks' and ((r->>'data_status') in ('LIVE','PROVISIONAL','FINAL') or r?'finalized_at')) then raise exception 'Owned refresh required';end if;
   end if;
   if p_operation='delete' and not coalesce(demo,false) then raise exception 'Only demo stat restoration may delete';end if;
  end loop;
  outrows:=outrows||got;
 end loop;
 if p_claim is not null then perform pickem.refresh_assert(p_claim);end if;
 return outrows;
end $$;

create or replace function pickem.refresh_commit(p_claim jsonb,p_payload jsonb) returns jsonb
language plpgsql security definer set search_path=pg_catalog,pickem,pg_temp as $$
declare j pickem.refresh_jobs;w pickem.weeks;r jsonb;k text;score_kind text;n timestamptz:=clock_timestamp();count_rows integer;
begin
 j:=pickem.refresh_assert(p_claim);select * into w from pickem.weeks where id=j.week_id;
 if jsonb_typeof(p_payload) is distinct from 'object' or p_payload->'version' is distinct from '1'::jsonb or octet_length(p_payload::text)>4000000 or
 (p_payload-array['version','games','stats','scores','score_status','week','runs','success'])<>'{}'::jsonb or
 jsonb_typeof(p_payload->'week') is distinct from 'object' or jsonb_typeof(p_payload->'success') is distinct from 'boolean' then raise exception 'Invalid refresh payload';end if;
 foreach k in array array['games','stats','scores','runs'] loop
  if jsonb_typeof(p_payload->k) is distinct from 'array' or jsonb_array_length(p_payload->k)>100 then raise exception 'Invalid refresh array';end if;
 end loop;
 if j.kind not in ('stats','games','durable','final') then raise exception 'Not a scoring owner';end if;
 if j.kind<>'final' and (w.data_status='FINAL' or p_payload->'week'->>'data_status'='FINAL' or p_payload->'week'?'finalized_at' or p_payload->>'score_status'='FINAL') then raise exception 'Final phase protected';end if;
 if w.data_status='PROVISIONAL' and (p_payload->>'score_status'='LIVE' or p_payload->'week'->>'data_status'='LIVE') then raise exception 'Cannot reopen provisional phase';end if;
 if j.kind='games' and (p_payload->'stats'<>'[]'::jsonb or p_payload->'scores'<>'[]'::jsonb or p_payload->'week'<>'{}'::jsonb) then raise exception 'Game lane cannot write scores';end if;
 if ((p_payload->'week')-array['data_status','last_data_refresh_at','finalized_at','data_message'])<>'{}'::jsonb then raise exception 'Unknown week field';end if;
 perform set_config('pickem.refresh_protocol','1',true);perform set_config('pickem.refresh_week',j.week_id::text,true);
 for r in select value from jsonb_array_elements(p_payload->'games') loop
  if jsonb_typeof(r) is distinct from 'object' or (r-array['provider_event_id','home_team','away_team','kickoff_at','is_eligible','game_status','period','game_clock','home_score','away_score','completed','over_under','spread','favored_team','provider_updated_at'])<>'{}'::jsonb then raise exception 'Invalid game fields';end if;
  perform pickem.refresh_edit('nfl_games','upsert',jsonb_build_array(r||jsonb_build_object('week_id',j.week_id)),'[]','week_id,provider_event_id',p_claim);
 end loop;
 foreach k in array array['stats','scores'] loop
  for r in select value from jsonb_array_elements(p_payload->k) loop
   if jsonb_typeof(r) is distinct from 'object' or (r-array['pool_player_id','source','source_player_id','raw_stats','points','breakdown','game_status'])<>'{}'::jsonb or jsonb_typeof(r->'points') is distinct from 'number' or abs((r->>'points')::numeric)>=100000 or jsonb_typeof(r->'raw_stats') is distinct from 'object' or jsonb_typeof(r->'breakdown') is distinct from 'object' then raise exception 'Invalid stat fields';end if;
   if not exists(select 1 from pickem.player_pool where id=(r->>'pool_player_id')::uuid and week_id=j.week_id) then raise exception 'Pool membership changed';end if;
   if k='stats' then
    perform pickem.refresh_edit('player_week_stats','upsert',jsonb_build_array(r||jsonb_build_object('week_id',j.week_id,'updated_at',n)),'[]','week_id,pool_player_id',p_claim);
   else
    score_kind:=p_payload->>'score_status';if score_kind is null or score_kind not in ('LIVE','PROVISIONAL','FINAL') then raise exception 'Invalid score status';end if;
    update pickem.player_pool set score_total=coalesce(manual_score_override,(r->>'points')::numeric),score_status=score_kind,score_breakdown=r->'breakdown',game_status=r->>'game_status',espn_player_id=coalesce(nullif(r->>'source_player_id',''),espn_player_id),score_updated_at=n,provider_updated_at=n where id=(r->>'pool_player_id')::uuid and week_id=j.week_id;
   end if;
  end loop;
 end loop;
 if p_payload->'week'<>'{}'::jsonb then
  perform pickem.refresh_edit('weeks','update',jsonb_build_array(p_payload->'week'),jsonb_build_array(jsonb_build_object('column','id','op','eq','value',j.week_id)),'',p_claim);
 end if;
 for r in select value from jsonb_array_elements(p_payload->'runs') loop
  if jsonb_typeof(r) is distinct from 'object' or (r-array['id','run_type','provider','started_at','completed_at','success','message','metadata'])<>'{}'::jsonb or coalesce(r->>'run_type','') not in ('live_game_state','live_player_stats','live_scores','final_reconcile') then raise exception 'Invalid run';end if;
  insert into pickem.data_runs(id,week_id,run_type,provider,started_at,completed_at,success,message,metadata)
  select id,j.week_id,run_type,provider,started_at,completed_at,success,message,metadata from jsonb_populate_record(null::pickem.data_runs,r);
 end loop;
 perform pickem.refresh_assert(p_claim);
 if p_payload->'week'->>'data_status'='FINAL' then update pickem.refresh_jobs set archive_pending=true where week_id=j.week_id;end if;
 perform pickem.refresh_release(p_claim,(p_payload->>'success')::boolean);
 return jsonb_build_object('committed',true,'revision',pickem.refresh_revision());
end $$;

create or replace function pickem.refresh_override(p_week_id uuid,p_pool_id uuid,p_score numeric,p_note text default null) returns jsonb
language plpgsql security definer set search_path=pg_catalog,pickem,pg_temp as $$
declare w pickem.weeks;r pickem.player_pool;provider_score numeric;
begin
 perform pickem.refresh_lock();select * into w from pickem.weeks where id=p_week_id;
 if w.id is null or w.published_at is null or clock_timestamp()<w.locks_at then raise exception 'Score overrides require a published, locked week';end if;
 if p_score is not null and (p_score::text in ('NaN','Infinity','-Infinity') or p_score< -100 or p_score>250 or length(trim(coalesce(p_note,'')))<3) then raise exception 'Invalid score override';end if;
 select points into provider_score from pickem.player_week_stats where week_id=p_week_id and pool_player_id=p_pool_id;
 perform set_config('pickem.refresh_protocol','1',true);
 update pickem.player_pool set manual_score_override=p_score,manual_override_at=case when p_score is not null then clock_timestamp() end,manual_override_note=case when p_score is not null then p_note end,score_total=coalesce(p_score,provider_score),score_updated_at=clock_timestamp() where id=p_pool_id and week_id=p_week_id returning * into r;
 if r.id is null then raise exception 'Pool player not found';end if;
 if w.data_status='FINAL' then insert into pickem.refresh_jobs(week_id,archive_pending) values(p_week_id,true) on conflict(week_id) do update set archive_pending=true;end if;
 return to_jsonb(r);
end $$;

create or replace function pickem.refresh_archive(p_week_id uuid,p_expected_revision bigint,p_rows jsonb,p_champions jsonb,p_stamp timestamptz) returns jsonb
language plpgsql security definer set search_path=pg_catalog,pickem,pg_temp as $$
declare w pickem.weeks;r jsonb;
begin
 perform pickem.refresh_lock();
 if p_expected_revision is distinct from pickem.refresh_revision() then raise exception 'Archive input changed' using errcode='40001';end if;
 select * into w from pickem.weeks where id=p_week_id;
 if w.id is null or w.data_status<>'FINAL' then raise exception 'Archive requires final week';end if;
 for r in select value from jsonb_array_elements(p_rows) loop
  if (r->>'week_id')::uuid is distinct from w.id or (r->>'season')::integer is distinct from w.season or (r->>'nfl_week')::integer is distinct from w.nfl_week then raise exception 'Archive identity mismatch';end if;
 end loop;
 for r in select value from jsonb_array_elements(p_champions) loop
  if w.nfl_week<>18 or (r->>'season')::integer is distinct from w.season then raise exception 'Champion identity mismatch';end if;
 end loop;
 perform pickem.refresh_edit('weekly_results','upsert',p_rows,'[]','week_id,player_id',null,pickem.refresh_revision());
 perform pickem.refresh_edit('season_champions','upsert',p_champions,'[]','season,player_id',null,pickem.refresh_revision());
 perform set_config('pickem.refresh_protocol','1',true);
 update pickem.weeks set results_archived_at=p_stamp where id=p_week_id;
 update pickem.refresh_jobs set archive_pending=false where week_id=p_week_id;
 return jsonb_build_object('archived',true,'revision',pickem.refresh_revision());
end $$;

create or replace function pickem.refresh_purge(p_season integer,p_before integer,p_claim jsonb) returns jsonb
language plpgsql security definer set search_path=pg_catalog,pickem,pg_temp as $$
declare j pickem.refresh_jobs;w pickem.weeks;r record;outrows jsonb:='[]';
begin
 j:=pickem.refresh_assert(p_claim);select * into w from pickem.weeks where id=j.week_id;
 if j.kind<>'publish' or w.season<>p_season or w.nfl_week<>p_before or w.published_at is null then raise exception 'Publication owner required';end if;
 perform set_config('pickem.refresh_protocol','1',true);
 for r in select id,nfl_week from pickem.weeks where season=p_season and not is_demo and nfl_week<p_before and finalized_at is not null and rosters_purged_at is null loop
  delete from pickem.lineups where week_id=r.id;
  update pickem.weeks set rosters_purged_at=clock_timestamp() where id=r.id;
  outrows:=outrows||jsonb_build_array(r.nfl_week);
 end loop;
 perform pickem.refresh_assert(p_claim);return outrows;
end $$;

do $$ declare r record;begin
 for r in select p.oid::regprocedure as sig,p.proname from pg_proc p join pg_namespace n on n.oid=p.pronamespace where n.nspname='pickem' and p.proname like 'refresh_%' and p.proname in ('refresh_lock','refresh_statement_guard','refresh_changed','refresh_assert','refresh_claim','refresh_release','refresh_read_week','refresh_revision','refresh_set_background','refresh_edit','refresh_commit','refresh_override','refresh_archive','refresh_purge','refresh_pending_archives') loop
  execute format('revoke all on function %s from public,anon,authenticated,service_role',r.sig);
  if r.proname not in ('refresh_lock','refresh_statement_guard','refresh_changed','refresh_assert') then execute format('grant execute on function %s to service_role',r.sig);end if;
 end loop;
end $$;
notify pgrst,'reload schema';
commit;
