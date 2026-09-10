-- Teal's Sunday Pick'em v1.0.7 — Sunday Clock Broadcast + Commissioner Cleanup
-- Run once after 005_automation_hardening.sql.
-- Adds an optional, scoped read-only AWTRIX broadcast channel.
-- No service-role/secret key is ever exposed to the physical clock.

create extension if not exists pgcrypto;

grant usage on schema pickem to anon, authenticated;

create table if not exists pickem.clock_tokens (
  id uuid primary key default gen_random_uuid(),
  token_hash text not null unique,
  token_hint text not null,
  created_at timestamptz not null default now(),
  revoked_at timestamptz,
  last_seen_at timestamptz,
  last_ack_at timestamptz,
  last_event_id text
);

create table if not exists pickem.clock_week_settings (
  week_id uuid primary key references pickem.weeks(id) on delete cascade,
  welcome_enabled boolean not null default false,
  welcome_text text not null default '',
  party_enabled boolean not null default false,
  party_text text not null default '',
  custom_enabled boolean not null default false,
  custom_text text not null default '',
  updated_at timestamptz not null default now(),
  check (char_length(welcome_text) <= 240),
  check (char_length(party_text) <= 240),
  check (char_length(custom_text) <= 240)
);

create table if not exists pickem.clock_snapshots (
  week_id uuid primary key references pickem.weeks(id) on delete cascade,
  payload jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

create table if not exists pickem.clock_control (
  singleton boolean primary key default true check (singleton),
  test_week_id uuid references pickem.weeks(id) on delete set null,
  test_nonce text,
  test_until timestamptz,
  updated_at timestamptz not null default now()
);

insert into pickem.clock_control(singleton) values (true)
on conflict (singleton) do nothing;

alter table pickem.clock_tokens enable row level security;
alter table pickem.clock_week_settings enable row level security;
alter table pickem.clock_snapshots enable row level security;
alter table pickem.clock_control enable row level security;

revoke all on table pickem.clock_tokens from anon, authenticated;
revoke all on table pickem.clock_week_settings from anon, authenticated;
revoke all on table pickem.clock_snapshots from anon, authenticated;
revoke all on table pickem.clock_control from anon, authenticated;

grant all on table pickem.clock_tokens to service_role;
grant all on table pickem.clock_week_settings to service_role;
grant all on table pickem.clock_snapshots to service_role;
grant all on table pickem.clock_control to service_role;

-- The clock receives one already-safe display line at a time. It never receives
-- lineup rows, PINs, player IDs, commissioner data, or a database secret key.
create or replace function pickem.clock_feed(p_token text)
returns jsonb
language plpgsql
security definer
set search_path = pickem, public
as $$
declare
  v_token pickem.clock_tokens%rowtype;
  v_control pickem.clock_control%rowtype;
  v_week pickem.weeks%rowtype;
  v_settings pickem.clock_week_settings%rowtype;
  v_payload jsonb := '{}'::jsonb;
  v_local timestamp;
  v_minute integer;
  v_slot bigint;
  v_category text := '';
  v_text text := '';
  v_event_id text := '';
  v_arr jsonb;
  v_count integer := 0;
  v_index integer := 0;
  v_manual text[] := array[]::text[];
  v_test_slot bigint;
begin
  if coalesce(length(p_token), 0) < 20 then
    return jsonb_build_object('ok', false, 'active', false);
  end if;

  select * into v_token
  from pickem.clock_tokens
  where token_hash = encode(digest(p_token, 'sha256'), 'hex')
    and revoked_at is null
  order by created_at desc
  limit 1;

  if v_token.id is null then
    return jsonb_build_object('ok', false, 'active', false);
  end if;

  update pickem.clock_tokens set last_seen_at = now() where id = v_token.id;
  select * into v_control from pickem.clock_control where singleton = true;

  -- Test Clock is intentionally synthetic and read-only. It can run on any day
  -- and never changes real scores, standings, lineups, or NFL data.
  if v_control.test_until is not null and v_control.test_until > now() and v_control.test_nonce is not null then
    v_test_slot := floor(extract(epoch from now()) / 12)::bigint;
    case mod(v_test_slot, 4)
      when 0 then v_text := 'PICK''EM CLOCK TEST • CONNECTION OK';
      when 1 then v_text := 'WELCOME • SUNDAY CLOCK TEST';
      when 2 then v_text := 'PICK''EM LIVE • 1 PLAYER A 42.1 • 2 PLAYER B 39.8 • 3 PLAYER C 37.4';
      else v_text := 'NFL LIVE TEST • AWAY 21 • HOME 17 • Q3 4:22';
    end case;
    v_event_id := 'test:' || v_control.test_nonce || ':' || v_test_slot::text;
    return jsonb_build_object('ok', true, 'active', true, 'test', true, 'event_id', v_event_id, 'text', v_text);
  end if;

  -- Pick'em broadcast is Sunday-only: begin 10:30 AM ET (2.5h before lock)
  -- and stop at midnight after the Sunday slate.
  select * into v_week
  from pickem.weeks
  where is_demo = false
    and now() >= locks_at - interval '150 minutes'
    and now() < locks_at + interval '11 hours'
  order by locks_at desc
  limit 1;

  if v_week.id is null then
    return jsonb_build_object('ok', true, 'active', false);
  end if;

  select * into v_settings from pickem.clock_week_settings where week_id = v_week.id;
  select payload into v_payload from pickem.clock_snapshots where week_id = v_week.id;
  v_payload := coalesce(v_payload, '{}'::jsonb);

  if coalesce(v_settings.welcome_enabled, false) and btrim(coalesce(v_settings.welcome_text, '')) <> '' then
    v_manual := array_append(v_manual, 'WELCOME • ' || btrim(v_settings.welcome_text));
  end if;
  if coalesce(v_settings.party_enabled, false) and btrim(coalesce(v_settings.party_text, '')) <> '' then
    v_manual := array_append(v_manual, 'SUNDAY AT TEAL''S • ' || btrim(v_settings.party_text));
  end if;
  if coalesce(v_settings.custom_enabled, false) and btrim(coalesce(v_settings.custom_text, '')) <> '' then
    v_manual := array_append(v_manual, btrim(v_settings.custom_text));
  end if;

  v_local := timezone('America/New_York', now());
  v_minute := extract(minute from v_local)::integer;
  v_slot := floor(extract(epoch from now()) / 300)::bigint;

  -- Before lock, never reveal picks, lineup ownership, weekly standings, or
  -- player-selection storylines. Only readiness and optional party messages.
  if now() < v_week.locks_at then
    if mod(floor(v_minute / 10)::integer, 2) = 0 and array_length(v_manual, 1) is not null then
      v_index := mod(floor(extract(epoch from now()) / 600)::integer, array_length(v_manual, 1)) + 1;
      v_text := v_manual[v_index];
      v_category := 'manual';
    else
      v_text := coalesce(v_payload->>'readiness', 'SUNDAY PICK''EM • PICKS LOCK 1 PM ET');
      v_category := 'readiness';
    end if;
  else
    -- Post-lock broadcast rhythm. The feed changes at most every five minutes;
    -- the AWTRIX script may poll more often without creating duplicate displays.
    case floor(v_minute / 5)::integer
      when 0 then v_category := 'weekly';
      when 1 then v_category := 'live_games';
      when 2 then v_category := 'player';
      when 3 then v_category := 'weekly';
      when 4 then v_category := case when v_week.nfl_week >= 2 then 'season' else 'pulse' end;
      when 5 then v_category := 'manual';
      when 6 then v_category := 'weekly';
      when 7 then v_category := 'live_games';
      when 8 then v_category := 'player';
      when 9 then v_category := 'weekly';
      when 10 then v_category := case when v_week.nfl_week >= 2 then 'season' else 'pulse' end;
      else v_category := 'manual';
    end case;

    if v_category = 'weekly' then
      if upper(coalesce(v_payload->>'data_status', '')) = 'FINAL' and coalesce(v_payload->>'champion', '') <> '' then
        v_text := v_payload->>'champion';
      else
        v_text := coalesce(v_payload->>'weekly', '');
      end if;
    elsif v_category = 'live_games' then
      v_text := coalesce(v_payload->>'live_games', '');
    elsif v_category = 'season' then
      v_text := coalesce(v_payload->>'season_text', '');
    elsif v_category = 'player' then
      v_arr := coalesce(v_payload->'player_updates', '[]'::jsonb);
      v_count := jsonb_array_length(v_arr);
      if v_count > 0 then
        v_index := mod(floor(extract(epoch from now()) / 300)::integer, v_count);
        v_text := v_arr->>v_index;
      end if;
    elsif v_category = 'pulse' then
      v_arr := coalesce(v_payload->'pulses', '[]'::jsonb);
      v_count := jsonb_array_length(v_arr);
      if v_count > 0 then
        v_index := mod(floor(extract(epoch from now()) / 300)::integer, v_count);
        v_text := v_arr->>v_index;
      end if;
    elsif v_category = 'manual' and array_length(v_manual, 1) is not null then
      v_index := mod(floor(extract(epoch from now()) / 1800)::integer, array_length(v_manual, 1)) + 1;
      v_text := v_manual[v_index];
    end if;

    -- Missing categories gracefully fall back to app-owned automatic content.
    if btrim(coalesce(v_text, '')) = '' then
      v_category := 'fallback';
      v_text := coalesce(nullif(v_payload->>'weekly', ''), nullif(v_payload->>'live_games', ''), nullif(v_payload->>'readiness', ''), 'SUNDAY PICK''EM');
    end if;
  end if;

  v_text := left(regexp_replace(coalesce(v_text, ''), E'[\\n\\r\\t]+', ' ', 'g'), 420);
  v_event_id := v_week.id::text || ':' || v_slot::text || ':' || v_category;
  return jsonb_build_object(
    'ok', true,
    'active', true,
    'test', false,
    'week', v_week.nfl_week,
    'event_id', v_event_id,
    'category', v_category,
    'text', v_text
  );
end;
$$;

create or replace function pickem.clock_ack(p_token text, p_event_id text)
returns jsonb
language plpgsql
security definer
set search_path = pickem, public
as $$
declare
  v_id uuid;
begin
  select id into v_id
  from pickem.clock_tokens
  where token_hash = encode(digest(p_token, 'sha256'), 'hex')
    and revoked_at is null
  order by created_at desc
  limit 1;

  if v_id is null then
    return jsonb_build_object('ok', false);
  end if;

  update pickem.clock_tokens
  set last_ack_at = now(), last_event_id = left(coalesce(p_event_id, ''), 180)
  where id = v_id;
  return jsonb_build_object('ok', true);
end;
$$;

revoke all on function pickem.clock_feed(text) from public;
revoke all on function pickem.clock_ack(text, text) from public;
grant execute on function pickem.clock_feed(text) to anon, authenticated;
grant execute on function pickem.clock_ack(text, text) to anon, authenticated;

comment on column pickem.clock_tokens.token_hash is 'SHA-256 of scoped/revocable AWTRIX token. Plaintext token is never stored.';
comment on function pickem.clock_feed(text) is 'Scoped, read-only Sunday display feed. Pre-lock output does not reveal picks.';

insert into pickem.app_meta(key, value)
values ('schema_version', '{"version":"1.0.7"}'::jsonb)
on conflict (key) do update set value=excluded.value, updated_at=now();
