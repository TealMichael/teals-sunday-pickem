-- Teal's Sunday Pick'em v0.3.0 — Gate 3 NFL Data
-- Run AFTER 002_gate2_weekly_game.sql in the existing shared Yahtzee Supabase project.
-- All objects remain isolated inside the `pickem` schema.

-- -------------------------
-- Weekly data-state metadata
-- -------------------------
alter table pickem.weeks
  add column if not exists data_status text not null default 'WAITING',
  add column if not exists last_data_refresh_at timestamptz,
  add column if not exists finalized_at timestamptz,
  add column if not exists data_message text;

alter table pickem.weeks drop constraint if exists weeks_data_status_check;
alter table pickem.weeks add constraint weeks_data_status_check
  check (data_status in ('WAITING','POOL_READY','LIVE','PROVISIONAL','FINAL','ERROR'));

-- -------------------------
-- Provider/scoring metadata on the weekly pool
-- -------------------------
alter table pickem.player_pool
  add column if not exists sleeper_player_id text,
  add column if not exists espn_player_id text,
  add column if not exists raw_injury_status text,
  add column if not exists schedule_eligible boolean not null default true,
  add column if not exists schedule_note text,
  add column if not exists score_total numeric(8,3),
  add column if not exists score_status text not null default 'SCHEDULED',
  add column if not exists score_breakdown jsonb not null default '{}'::jsonb,
  add column if not exists game_status text,
  add column if not exists score_updated_at timestamptz,
  add column if not exists manual_score_override numeric(8,3),
  add column if not exists manual_override_at timestamptz,
  add column if not exists manual_override_note text,
  add column if not exists provider_updated_at timestamptz;

alter table pickem.player_pool drop constraint if exists player_pool_score_status_check;
alter table pickem.player_pool add constraint player_pool_score_status_check
  check (score_status in ('SCHEDULED','LIVE','PROVISIONAL','FINAL'));

create index if not exists player_pool_sleeper_idx on pickem.player_pool(sleeper_player_id);
create index if not exists player_pool_espn_idx on pickem.player_pool(espn_player_id);

-- -------------------------
-- Normalized NFL schedule cache
-- -------------------------
create table if not exists pickem.nfl_games (
  id uuid primary key default gen_random_uuid(),
  week_id uuid not null references pickem.weeks(id) on delete cascade,
  provider_event_id text not null,
  home_team text not null,
  away_team text not null,
  kickoff_at timestamptz not null,
  is_eligible boolean not null default false,
  game_status text not null default 'SCHEDULED',
  period integer,
  game_clock text,
  home_score integer,
  away_score integer,
  completed boolean not null default false,
  over_under numeric(7,2),
  spread numeric(7,2),
  favored_team text,
  provider_updated_at timestamptz not null default now(),
  unique (week_id, provider_event_id)
);

alter table pickem.nfl_games drop constraint if exists nfl_games_status_check;
alter table pickem.nfl_games add constraint nfl_games_status_check
  check (game_status in ('SCHEDULED','LIVE','FINAL','POSTPONED','CANCELED'));

create index if not exists nfl_games_week_kickoff_idx on pickem.nfl_games(week_id, kickoff_at);

-- -------------------------
-- Daily player / injury cache (Sleeper first, provider-agnostic storage)
-- -------------------------
create table if not exists pickem.nfl_players (
  id uuid primary key default gen_random_uuid(),
  sleeper_player_id text unique,
  canonical_key text not null,
  full_name text not null,
  position text not null,
  team_abbr text,
  active boolean not null default true,
  injury_status text,
  availability_status text not null default 'HEALTHY',
  depth_order integer,
  metadata jsonb not null default '{}'::jsonb,
  last_synced_at timestamptz not null default now(),
  check (position in ('QB','RB','WR','TE','K')),
  check (availability_status in ('HEALTHY','QUESTIONABLE','OUT'))
);

create index if not exists nfl_players_lookup_idx on pickem.nfl_players(position, team_abbr, canonical_key);

-- -------------------------
-- Per-week player stat/scoring snapshots
-- -------------------------
create table if not exists pickem.player_week_stats (
  id uuid primary key default gen_random_uuid(),
  week_id uuid not null references pickem.weeks(id) on delete cascade,
  pool_player_id uuid not null references pickem.player_pool(id) on delete cascade,
  source text not null,
  source_player_id text,
  raw_stats jsonb not null default '{}'::jsonb,
  points numeric(8,3) not null default 0,
  breakdown jsonb not null default '{}'::jsonb,
  game_status text,
  updated_at timestamptz not null default now(),
  unique (week_id, pool_player_id)
);

create index if not exists player_week_stats_week_idx on pickem.player_week_stats(week_id);

-- -------------------------
-- Idempotent scheduler/run history
-- -------------------------
create table if not exists pickem.data_runs (
  id uuid primary key default gen_random_uuid(),
  week_id uuid references pickem.weeks(id) on delete cascade,
  run_type text not null,
  provider text,
  started_at timestamptz not null default now(),
  completed_at timestamptz,
  success boolean,
  message text,
  metadata jsonb not null default '{}'::jsonb
);

create index if not exists data_runs_type_time_idx on pickem.data_runs(run_type, started_at desc);
create index if not exists data_runs_week_type_idx on pickem.data_runs(week_id, run_type, started_at desc);

-- Gate 3 backend tables remain server-only. The Streamlit app and GitHub Action
-- use the project's secret/service role. Browser roles receive no direct access.
alter table pickem.nfl_games enable row level security;
alter table pickem.nfl_players enable row level security;
alter table pickem.player_week_stats enable row level security;
alter table pickem.data_runs enable row level security;

revoke all on table pickem.nfl_games from anon, authenticated;
revoke all on table pickem.nfl_players from anon, authenticated;
revoke all on table pickem.player_week_stats from anon, authenticated;
revoke all on table pickem.data_runs from anon, authenticated;

grant all on table pickem.nfl_games to service_role;
grant all on table pickem.nfl_players to service_role;
grant all on table pickem.player_week_stats to service_role;
grant all on table pickem.data_runs to service_role;

-- Existing Gate 2 tables gained columns; keep service-role access explicit.
grant all on table pickem.weeks to service_role;
grant all on table pickem.player_pool to service_role;

-- Reset real Week 1 data state without touching any Gate 2 lineups or demo rows.
update pickem.weeks
set data_status = case when published_at is null then 'WAITING' else 'POOL_READY' end,
    data_message = null
where season = 2026 and nfl_week = 1 and is_demo = false;

insert into pickem.app_meta(key, value)
values ('schema_version', '{"version":"0.3.0"}'::jsonb)
on conflict (key) do update set value=excluded.value, updated_at=now();
