-- Teal's Sunday Pick'em v0.4.0 — Gate 4 Live Sunday + Season
-- Run AFTER 003_gate3_nfl_data.sql.
-- Adds finalized weekly-result history and season champion archive.

alter table pickem.weeks
  add column if not exists results_archived_at timestamptz,
  add column if not exists rosters_purged_at timestamptz;

create table if not exists pickem.weekly_results (
  id uuid primary key default gen_random_uuid(),
  week_id uuid not null references pickem.weeks(id) on delete cascade,
  season integer not null,
  nfl_week integer not null,
  player_id uuid references pickem.players(id) on delete set null,
  nickname_snapshot text not null,
  emoji_snapshot text not null,
  weekly_score numeric(8,1) not null default 0,
  finish_rank integer not null check (finish_rank >= 1),
  season_points integer not null default 0 check (season_points >= 0),
  is_champion boolean not null default false,
  finalized_at timestamptz not null default now(),
  unique (week_id, player_id)
);

create index if not exists weekly_results_season_week_idx
  on pickem.weekly_results(season, nfl_week, finish_rank);
create index if not exists weekly_results_player_idx
  on pickem.weekly_results(player_id, season, nfl_week);

create table if not exists pickem.season_champions (
  id uuid primary key default gen_random_uuid(),
  season integer not null,
  player_id uuid references pickem.players(id) on delete set null,
  nickname_snapshot text not null,
  emoji_snapshot text not null,
  season_points integer not null,
  total_fantasy_points numeric(10,1) not null,
  awarded_at timestamptz not null default now(),
  unique (season, player_id)
);

create index if not exists season_champions_season_idx on pickem.season_champions(season);

alter table pickem.weekly_results enable row level security;
alter table pickem.season_champions enable row level security;
revoke all on table pickem.weekly_results from anon, authenticated;
revoke all on table pickem.season_champions from anon, authenticated;
grant all on table pickem.weekly_results to service_role;
grant all on table pickem.season_champions to service_role;

grant all on table pickem.weeks to service_role;

insert into pickem.app_meta(key, value)
values ('schema_version', '{"version":"0.4.0"}'::jsonb)
on conflict (key) do update set value=excluded.value, updated_at=now();
