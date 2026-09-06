-- Teal's Sunday Pick'em v0.2.0 — Gate 2 Weekly Game
-- Run AFTER 001_gate1_foundation.sql in the existing shared Yahtzee Supabase project.
-- All new objects remain isolated inside the `pickem` schema.

alter table pickem.players
  add column if not exists onboarding_completed_at timestamptz;

create table if not exists pickem.weeks (
  id uuid primary key default gen_random_uuid(),
  season integer not null,
  nfl_week integer not null,
  label text not null,
  opens_at timestamptz not null,
  locks_at timestamptz not null,
  published_at timestamptz,
  is_demo boolean not null default false,
  created_at timestamptz not null default now(),
  unique (season, nfl_week, is_demo),
  check (locks_at > opens_at)
);

create table if not exists pickem.player_pool (
  id uuid primary key default gen_random_uuid(),
  week_id uuid not null references pickem.weeks(id) on delete cascade,
  position text not null check (position in ('QB','RB','WR','TE','K')),
  slot_rank integer not null check (slot_rank between 1 and 10),
  player_name text not null,
  nfl_player_id text,
  team_abbr text not null,
  opponent_abbr text not null,
  kickoff_at timestamptz not null,
  is_visible boolean not null default false,
  availability_status text not null default 'HEALTHY' check (availability_status in ('HEALTHY','QUESTIONABLE','OUT')),
  created_at timestamptz not null default now(),
  unique (week_id, position, slot_rank)
);

create index if not exists player_pool_week_position_idx on pickem.player_pool(week_id, position, slot_rank);

create table if not exists pickem.lineups (
  id uuid primary key default gen_random_uuid(),
  week_id uuid not null references pickem.weeks(id) on delete cascade,
  player_id uuid not null references pickem.players(id) on delete cascade,
  confirmed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (week_id, player_id)
);

create table if not exists pickem.lineup_picks (
  id uuid primary key default gen_random_uuid(),
  lineup_id uuid not null references pickem.lineups(id) on delete cascade,
  position text not null check (position in ('QB','RB','WR','TE','K')),
  pool_player_id uuid not null references pickem.player_pool(id),
  emergency_pool_player_id uuid references pickem.player_pool(id),
  updated_at timestamptz not null default now(),
  unique (lineup_id, position),
  check (emergency_pool_player_id is null or emergency_pool_player_id <> pool_player_id)
);

create index if not exists lineups_week_idx on pickem.lineups(week_id);
create index if not exists lineup_picks_lineup_idx on pickem.lineup_picks(lineup_id);

-- Database-level guard: even service-role app bugs cannot alter picks after the universal lock.
create or replace function pickem.guard_lineup_pick()
returns trigger
language plpgsql
set search_path = pickem, public, pg_temp
as $$
declare
  v_lineup pickem.lineups%rowtype;
  v_week pickem.weeks%rowtype;
  v_starter pickem.player_pool%rowtype;
  v_backup pickem.player_pool%rowtype;
begin
  select * into v_lineup from pickem.lineups where id = coalesce(new.lineup_id, old.lineup_id);
  select * into v_week from pickem.weeks where id = v_lineup.week_id;

  if now() < v_week.opens_at and not v_week.is_demo then
    raise exception 'Picks are not open yet.' using errcode = 'P0001';
  end if;

  if now() >= v_week.locks_at then
    raise exception 'Picks are locked for this week.' using errcode = 'P0001';
  end if;

  if tg_op <> 'DELETE' then
    select * into v_starter from pickem.player_pool where id = new.pool_player_id;
    if v_starter.id is null or v_starter.week_id <> v_lineup.week_id or v_starter.position <> new.position or not v_starter.is_visible then
      raise exception 'Starter does not belong to this weekly position pool.' using errcode = 'P0001';
    end if;
    if v_starter.availability_status = 'OUT' then
      raise exception 'OUT players cannot be selected.' using errcode = 'P0001';
    end if;

    if new.emergency_pool_player_id is not null then
      select * into v_backup from pickem.player_pool where id = new.emergency_pool_player_id;
      if v_backup.id is null or v_backup.week_id <> v_lineup.week_id or v_backup.position <> new.position or not v_backup.is_visible then
        raise exception 'Emergency backup does not belong to this weekly position pool.' using errcode = 'P0001';
      end if;
      if v_backup.availability_status = 'OUT' then
        raise exception 'OUT players cannot be emergency backups.' using errcode = 'P0001';
      end if;
    end if;
  end if;
  if tg_op = 'DELETE' then
    return old;
  end if;
  return new;
end;
$$;

drop trigger if exists trg_guard_lineup_pick on pickem.lineup_picks;
create trigger trg_guard_lineup_pick
before insert or update or delete on pickem.lineup_picks
for each row execute function pickem.guard_lineup_pick();

alter table pickem.weeks enable row level security;
alter table pickem.player_pool enable row level security;
alter table pickem.lineups enable row level security;
alter table pickem.lineup_picks enable row level security;

revoke all on table pickem.weeks from anon, authenticated;
revoke all on table pickem.player_pool from anon, authenticated;
revoke all on table pickem.lineups from anon, authenticated;
revoke all on table pickem.lineup_picks from anon, authenticated;

grant all on table pickem.weeks to service_role;
grant all on table pickem.player_pool to service_role;
grant all on table pickem.lineups to service_role;
grant all on table pickem.lineup_picks to service_role;

-- Real 2026 Week 1 shell. Gate 3 publishes the actual Top 5 at each position.
insert into pickem.weeks(season, nfl_week, label, opens_at, locks_at, published_at, is_demo)
values (2026, 1, 'Week 1', '2026-09-08 12:00:00-04', '2026-09-13 13:00:00-04', null, false)
on conflict (season, nfl_week, is_demo) do update
set label = excluded.label, opens_at = excluded.opens_at, locks_at = excluded.locks_at;

-- Isolated build-test week so Gate 2 can be acceptance-tested before Tuesday.
insert into pickem.weeks(season, nfl_week, label, opens_at, locks_at, published_at, is_demo)
values (2026, 0, 'Gate 2 Test Week', '2026-01-01 00:00:00-05', '2099-01-01 13:00:00-05', now(), true)
on conflict (season, nfl_week, is_demo) do update
set label = excluded.label, opens_at = excluded.opens_at, locks_at = excluded.locks_at, published_at = now();

-- Seed 10 ranked demo choices per position; only ranks 1-5 are visible to players.
with demo as (
  select id from pickem.weeks where season=2026 and nfl_week=0 and is_demo=true limit 1
), seed(position, slot_rank, player_name, team_abbr, opponent_abbr, kickoff_at, availability_status) as (
  values
  ('QB',1,'Demo QB Alpha','BUF','NYJ','2026-09-13 13:00:00-04'::timestamptz,'HEALTHY'),
  ('QB',2,'Demo QB Bravo','BAL','CLE','2026-09-13 13:00:00-04'::timestamptz,'HEALTHY'),
  ('QB',3,'Demo QB Charlie','PHI','DAL','2026-09-13 13:00:00-04'::timestamptz,'HEALTHY'),
  ('QB',4,'Demo QB Delta','KC','LV','2026-09-13 16:25:00-04'::timestamptz,'QUESTIONABLE'),
  ('QB',5,'Demo QB Echo','CIN','PIT','2026-09-13 16:25:00-04'::timestamptz,'HEALTHY'),
  ('QB',6,'Demo QB Foxtrot','DET','GB','2026-09-13 16:25:00-04'::timestamptz,'HEALTHY'),
  ('QB',7,'Demo QB Golf','LAC','DEN','2026-09-13 16:05:00-04'::timestamptz,'HEALTHY'),
  ('QB',8,'Demo QB Hotel','SF','SEA','2026-09-13 20:20:00-04'::timestamptz,'HEALTHY'),
  ('QB',9,'Demo QB India','TB','ATL','2026-09-13 13:00:00-04'::timestamptz,'HEALTHY'),
  ('QB',10,'Demo QB Juliet','MIA','NE','2026-09-13 13:00:00-04'::timestamptz,'HEALTHY'),
  ('RB',1,'Demo RB Alpha','DET','GB','2026-09-13 16:25:00-04'::timestamptz,'HEALTHY'),
  ('RB',2,'Demo RB Bravo','PHI','DAL','2026-09-13 13:00:00-04'::timestamptz,'HEALTHY'),
  ('RB',3,'Demo RB Charlie','ATL','TB','2026-09-13 13:00:00-04'::timestamptz,'QUESTIONABLE'),
  ('RB',4,'Demo RB Delta','BAL','CLE','2026-09-13 13:00:00-04'::timestamptz,'HEALTHY'),
  ('RB',5,'Demo RB Echo','SF','SEA','2026-09-13 20:20:00-04'::timestamptz,'HEALTHY'),
  ('RB',6,'Demo RB Foxtrot','IND','HOU','2026-09-13 13:00:00-04'::timestamptz,'HEALTHY'),
  ('RB',7,'Demo RB Golf','NYJ','BUF','2026-09-13 13:00:00-04'::timestamptz,'HEALTHY'),
  ('RB',8,'Demo RB Hotel','LAR','ARI','2026-09-13 16:05:00-04'::timestamptz,'HEALTHY'),
  ('RB',9,'Demo RB India','MIA','NE','2026-09-13 13:00:00-04'::timestamptz,'HEALTHY'),
  ('RB',10,'Demo RB Juliet','KC','LV','2026-09-13 16:25:00-04'::timestamptz,'OUT'),
  ('WR',1,'Demo WR Alpha','MIN','CHI','2026-09-13 13:00:00-04'::timestamptz,'HEALTHY'),
  ('WR',2,'Demo WR Bravo','CIN','PIT','2026-09-13 16:25:00-04'::timestamptz,'HEALTHY'),
  ('WR',3,'Demo WR Charlie','DAL','PHI','2026-09-13 13:00:00-04'::timestamptz,'HEALTHY'),
  ('WR',4,'Demo WR Delta','MIA','NE','2026-09-13 13:00:00-04'::timestamptz,'HEALTHY'),
  ('WR',5,'Demo WR Echo','LAR','ARI','2026-09-13 16:05:00-04'::timestamptz,'HEALTHY'),
  ('WR',6,'Demo WR Foxtrot','DET','GB','2026-09-13 16:25:00-04'::timestamptz,'HEALTHY'),
  ('WR',7,'Demo WR Golf','SEA','SF','2026-09-13 20:20:00-04'::timestamptz,'HEALTHY'),
  ('WR',8,'Demo WR Hotel','BUF','NYJ','2026-09-13 13:00:00-04'::timestamptz,'HEALTHY'),
  ('WR',9,'Demo WR India','TB','ATL','2026-09-13 13:00:00-04'::timestamptz,'HEALTHY'),
  ('WR',10,'Demo WR Juliet','LAC','DEN','2026-09-13 16:05:00-04'::timestamptz,'HEALTHY'),
  ('TE',1,'Demo TE Alpha','KC','LV','2026-09-13 16:25:00-04'::timestamptz,'HEALTHY'),
  ('TE',2,'Demo TE Bravo','DET','GB','2026-09-13 16:25:00-04'::timestamptz,'HEALTHY'),
  ('TE',3,'Demo TE Charlie','SF','SEA','2026-09-13 20:20:00-04'::timestamptz,'QUESTIONABLE'),
  ('TE',4,'Demo TE Delta','BAL','CLE','2026-09-13 13:00:00-04'::timestamptz,'HEALTHY'),
  ('TE',5,'Demo TE Echo','BUF','NYJ','2026-09-13 13:00:00-04'::timestamptz,'HEALTHY'),
  ('TE',6,'Demo TE Foxtrot','ARI','LAR','2026-09-13 16:05:00-04'::timestamptz,'HEALTHY'),
  ('TE',7,'Demo TE Golf','DAL','PHI','2026-09-13 13:00:00-04'::timestamptz,'HEALTHY'),
  ('TE',8,'Demo TE Hotel','GB','DET','2026-09-13 16:25:00-04'::timestamptz,'HEALTHY'),
  ('TE',9,'Demo TE India','ATL','TB','2026-09-13 13:00:00-04'::timestamptz,'HEALTHY'),
  ('TE',10,'Demo TE Juliet','DEN','LAC','2026-09-13 16:05:00-04'::timestamptz,'HEALTHY'),
  ('K',1,'Demo K Alpha','DET','GB','2026-09-13 16:25:00-04'::timestamptz,'HEALTHY'),
  ('K',2,'Demo K Bravo','KC','LV','2026-09-13 16:25:00-04'::timestamptz,'HEALTHY'),
  ('K',3,'Demo K Charlie','BUF','NYJ','2026-09-13 13:00:00-04'::timestamptz,'HEALTHY'),
  ('K',4,'Demo K Delta','PHI','DAL','2026-09-13 13:00:00-04'::timestamptz,'HEALTHY'),
  ('K',5,'Demo K Echo','CIN','PIT','2026-09-13 16:25:00-04'::timestamptz,'HEALTHY'),
  ('K',6,'Demo K Foxtrot','SF','SEA','2026-09-13 20:20:00-04'::timestamptz,'HEALTHY'),
  ('K',7,'Demo K Golf','MIA','NE','2026-09-13 13:00:00-04'::timestamptz,'HEALTHY'),
  ('K',8,'Demo K Hotel','LAR','ARI','2026-09-13 16:05:00-04'::timestamptz,'HEALTHY'),
  ('K',9,'Demo K India','TB','ATL','2026-09-13 13:00:00-04'::timestamptz,'HEALTHY'),
  ('K',10,'Demo K Juliet','LAC','DEN','2026-09-13 16:05:00-04'::timestamptz,'HEALTHY')
)
insert into pickem.player_pool(week_id, position, slot_rank, player_name, team_abbr, opponent_abbr, kickoff_at, is_visible, availability_status)
select demo.id, seed.position, seed.slot_rank, seed.player_name, seed.team_abbr, seed.opponent_abbr, seed.kickoff_at, seed.slot_rank <= 5, seed.availability_status
from demo cross join seed
on conflict (week_id, position, slot_rank) do update
set player_name=excluded.player_name, team_abbr=excluded.team_abbr, opponent_abbr=excluded.opponent_abbr,
    kickoff_at=excluded.kickoff_at, is_visible=excluded.is_visible, availability_status=excluded.availability_status;

insert into pickem.app_meta(key, value)
values ('schema_version', '{"version":"0.2.0"}'::jsonb)
on conflict (key) do update set value=excluded.value, updated_at=now();
