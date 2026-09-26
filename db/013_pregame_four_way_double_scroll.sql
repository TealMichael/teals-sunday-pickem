-- Teal's Sunday Pick'em v1.0.7-hotfix7.18
-- Sunday Pregame Four-Way Rotation + Double-Scroll Support
--
-- Focused clock-feed migration. No lineup, scoring-formula, player-pool, auth,
-- or fantasy-point persistence changes. Safe to rerun after the existing Sunday
-- clock migrations and the optional Commissioner melody migration.
--
-- Changes:
--   * Saturday remains NFL Sunday Preview every 15 minutes all day ET.
--   * Sunday 10:30 AM-1:00 PM ET rotates four privacy-safe categories:
--       NFL Sunday Preview -> Commissioner -> Pick'em Readiness -> Season Standings.
--     The four-way pattern repeats every 20 minutes.
--   * Sunday post-lock cadence is unchanged from Hotfix 7.17.
--   * Caleb 4K Watch remains parked.
--   * Double-scroll behavior is implemented only in the AWTRIX script for
--     preview, live_games, and weekly categories; the feed content is unchanged.
--   * Token validation, melody wrapper, scoring, lineups, and event ACKs stay intact.

begin;

create or replace function pickem.clock_feed(p_token text)
returns jsonb
language plpgsql
security definer
set search_path = pickem, public, extensions, pg_temp
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
  v_color text := '#FFFFFF';
  v_fragments jsonb := null;
  v_arr jsonb;
  v_arr_rich jsonb;
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

  -- Synthetic read-only Test Clock. It now demonstrates the mixed-color fragment
  -- design without touching real scores, standings, lineups, or NFL data.
  if v_control.test_until is not null and v_control.test_until > now() and v_control.test_nonce is not null then
    v_test_slot := floor(extract(epoch from now()) / 12)::bigint;
    case mod(v_test_slot, 5)
      when 0 then
        v_text := 'PICK''EM CLOCK TEST • CONNECTION OK';
        v_fragments := jsonb_build_array(
          jsonb_build_object('text', 'PICK''EM CLOCK TEST • ', 'color', '2DD4BF'),
          jsonb_build_object('text', 'CONNECTION OK', 'color', '34C759')
        );
      when 1 then
        v_text := 'WELCOME • SUNDAY CLOCK TEST';
        v_fragments := jsonb_build_array(
          jsonb_build_object('text', 'WELCOME • ', 'color', 'FF9F0A'),
          jsonb_build_object('text', 'SUNDAY CLOCK TEST', 'color', 'FFFFFF')
        );
      when 2 then
        v_text := 'PICK''EM LIVE • 1 PLAYER A 42.1 • 2 PLAYER B 39.8 • 3 PLAYER C 37.4';
        v_fragments := jsonb_build_array(
          jsonb_build_object('text', 'PICK''EM LIVE • ', 'color', '2DD4BF'),
          jsonb_build_object('text', '1 PLAYER A', 'color', 'FFD700'),
          jsonb_build_object('text', ' 42.1', 'color', '2DD4BF'),
          jsonb_build_object('text', ' • 2 PLAYER B 39.8 • 3 PLAYER C 37.4', 'color', 'FFFFFF')
        );
      when 3 then
        v_text := 'NFL LIVE TEST • CHI 21 • MIN 17 • Q3 4:22';
        v_fragments := jsonb_build_array(
          jsonb_build_object('text', 'NFL LIVE TEST • ', 'color', 'FF453A'),
          jsonb_build_object('text', 'CHI', 'color', 'F56600'),
          jsonb_build_object('text', ' 21 • ', 'color', 'FFFFFF'),
          jsonb_build_object('text', 'MIN', 'color', 'A78BFA'),
          jsonb_build_object('text', ' 17 • Q3 4:22', 'color', 'FFFFFF')
        );
      else
        v_text := 'NFL SUNDAY PREVIEW TEST • 1 PM KC @ MIA • 4:25 PM BAL @ DAL';
        v_fragments := jsonb_build_array(
          jsonb_build_object('text', 'NFL SUNDAY PREVIEW TEST • ', 'color', '64D2FF'),
          jsonb_build_object('text', '1 PM ', 'color', 'FFFFFF'),
          jsonb_build_object('text', 'KC', 'color', 'E31837'),
          jsonb_build_object('text', ' @ MIA • 4:25 PM ', 'color', 'FFFFFF'),
          jsonb_build_object('text', 'BAL', 'color', '9E7CFF'),
          jsonb_build_object('text', ' @ DAL', 'color', 'FFFFFF')
        );
    end case;
    v_event_id := 'test:' || v_control.test_nonce || ':' || v_test_slot::text;
    return jsonb_build_object(
      'ok', true, 'active', true, 'test', true,
      'event_id', v_event_id, 'text', v_text, 'fragments', v_fragments
    );
  end if;

  v_local := timezone('America/New_York', now());

  -- Saturday preview lane: active for the entire local Saturday and emits one
  -- schedule-only NFL Sunday Preview event per 15-minute slot. It never exposes
  -- Pick'em ownership, lineups, fantasy points, standings, or other pre-lock data.
  if extract(dow from v_local)::integer = 6 then
    select * into v_week
    from pickem.weeks
    where is_demo = false
      and timezone('America/New_York', locks_at)::date = v_local::date + 1
    order by locks_at asc
    limit 1;

    if v_week.id is null then
      return jsonb_build_object('ok', true, 'active', false);
    end if;

    select payload into v_payload from pickem.clock_snapshots where week_id = v_week.id;
    v_payload := coalesce(v_payload, '{}'::jsonb);
    v_text := coalesce(v_payload->>'sunday_preview', '');
    v_fragments := v_payload->'sunday_preview_rich';
    if btrim(coalesce(v_text, '')) = '' then
      v_text := 'NFL SUNDAY PREVIEW • WEEK ' || v_week.nfl_week::text || ' • GAMES TOMORROW';
      v_fragments := jsonb_build_array(
        jsonb_build_object('text', 'NFL SUNDAY PREVIEW • ', 'color', '64D2FF'),
        jsonb_build_object('text', 'WEEK ' || v_week.nfl_week::text || ' • GAMES TOMORROW', 'color', 'FFFFFF')
      );
    end if;
    v_text := left(regexp_replace(coalesce(v_text, ''), E'[\n\r\t]+', ' ', 'g'), 420);
    v_slot := floor(extract(epoch from now()) / 900)::bigint;
    v_event_id := v_week.id::text || ':' || v_slot::text || ':preview';
    return jsonb_build_object(
      'ok', true, 'active', true, 'test', false,
      'week', v_week.nfl_week, 'event_id', v_event_id,
      'category', 'preview', 'text', v_text,
      'fragments', v_fragments, 'color', '#64D2FF'
    );
  end if;

  -- Sunday broadcast: begin 10:30 AM ET and stop at midnight.
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
    v_manual := array_append(v_manual, 'FROM THE COMMISH • ' || btrim(v_settings.custom_text));
  end if;

  v_minute := extract(minute from v_local)::integer;
  v_slot := floor(extract(epoch from now()) / 300)::bigint;

  -- Before lock, never reveal current-week picks, lineup ownership, weekly
  -- standings, or player-selection storylines. The pregame loop uses only four
  -- privacy-safe categories: Sunday schedule preview, Commissioner message,
  -- lineup readiness, and season standings from completed prior weeks.
  -- Five-minute slots form a 20-minute repeating cycle:
  --   :00 Preview  :05 Commissioner  :10 Readiness  :15 Season
  --   :20 Preview  :25 Commissioner  :30 Readiness  :35 Season
  --   :40 Preview  :45 Commissioner  :50 Readiness  :55 Season
  if now() < v_week.locks_at then
    case mod(floor(v_minute / 5)::integer, 4)
      when 0 then v_category := 'preview';
      when 1 then v_category := 'manual';
      when 2 then v_category := 'readiness';
      else v_category := 'season';
    end case;

    if v_category = 'preview' then
      v_text := coalesce(v_payload->>'sunday_preview', '');
      v_fragments := v_payload->'sunday_preview_rich';
      v_color := '#64D2FF';
    elsif v_category = 'manual' and array_length(v_manual, 1) is not null then
      v_index := mod(floor(extract(epoch from now()) / 1200)::integer, array_length(v_manual, 1)) + 1;
      v_text := v_manual[v_index];
      if position(' • ' in v_text) > 0 then
        v_fragments := jsonb_build_array(
          jsonb_build_object('text', split_part(v_text, ' • ', 1) || ' • ', 'color', 'FF9F0A'),
          jsonb_build_object('text', substring(v_text from position(' • ' in v_text) + 3), 'color', 'FFFFFF')
        );
      end if;
    elsif v_category = 'readiness' then
      v_text := coalesce(v_payload->>'readiness', 'SUNDAY PICK''EM • PICKS LOCK 1 PM ET');
      v_fragments := v_payload->'readiness_rich';
      if v_fragments is null then
        if lower(coalesce(v_payload->>'readiness_all_ready', 'false')) = 'true' then
          v_color := '#34C759';
        else
          v_color := '#FF9F0A';
        end if;
      end if;
    elsif v_category = 'season' then
      v_text := coalesce(v_payload->>'season_text', '');
      v_fragments := v_payload->'season_rich';
      v_color := '#64D2FF';
    end if;

    -- If a selected optional category is unavailable (for example no manual
    -- message is enabled, or Week 1 has no season standings yet), fall back to
    -- privacy-safe pregame content only. Never fall through to weekly scores.
    if btrim(coalesce(v_text, '')) = '' then
      if btrim(coalesce(v_payload->>'sunday_preview', '')) <> '' then
        v_category := 'preview';
        v_text := v_payload->>'sunday_preview';
        v_fragments := v_payload->'sunday_preview_rich';
        v_color := '#64D2FF';
      else
        v_category := 'readiness';
        v_text := coalesce(v_payload->>'readiness', 'SUNDAY PICK''EM • PICKS LOCK 1 PM ET');
        v_fragments := v_payload->'readiness_rich';
      end if;
    end if;
  else
    -- Post-lock broadcast rhythm. Feed category changes at most every five minutes.
    case floor(v_minute / 5)::integer
      when 0 then v_category := 'weekly';       -- :00
      when 1 then v_category := 'live_games';   -- :05
      when 2 then v_category := 'player';       -- :10
      when 3 then v_category := 'weekly';       -- :15
      when 4 then v_category := 'live_games';   -- :20
      when 5 then v_category := case
        when v_week.nfl_week >= 2 then 'season'
        else 'pulse'
      end;                                      -- :25
      when 6 then v_category := 'weekly';       -- :30
      when 7 then v_category := 'live_games';   -- :35
      when 8 then v_category := 'player';       -- :40
      when 9 then v_category := 'weekly';       -- :45
      when 10 then v_category := 'live_games';  -- :50
      else v_category := 'manual';              -- :55
    end case;

    if v_category = 'weekly' then
      if upper(coalesce(v_payload->>'data_status', '')) = 'FINAL' and coalesce(v_payload->>'champion', '') <> '' then
        v_text := v_payload->>'champion';
        v_fragments := v_payload->'champion_rich';
      else
        v_text := coalesce(v_payload->>'weekly', '');
        v_fragments := v_payload->'weekly_rich';
      end if;
    elsif v_category = 'live_games' then
      v_text := coalesce(v_payload->>'live_games', '');
      v_fragments := v_payload->'live_games_rich';
    elsif v_category = 'season' then
      v_text := coalesce(v_payload->>'season_text', '');
      v_fragments := v_payload->'season_rich';
    elsif v_category = 'player' then
      v_arr := coalesce(v_payload->'player_updates', '[]'::jsonb);
      v_arr_rich := coalesce(v_payload->'player_updates_rich', '[]'::jsonb);
      v_count := jsonb_array_length(v_arr);
      if v_count > 0 then
        v_index := mod(floor(extract(epoch from now()) / 300)::integer, v_count);
        v_text := v_arr->>v_index;
        if jsonb_array_length(v_arr_rich) > v_index then
          v_fragments := v_arr_rich->v_index;
        end if;
      end if;
    elsif v_category = 'pulse' then
      v_arr := coalesce(v_payload->'pulses', '[]'::jsonb);
      v_arr_rich := coalesce(v_payload->'pulses_rich', '[]'::jsonb);
      v_count := jsonb_array_length(v_arr);
      if v_count > 0 then
        v_index := mod(floor(extract(epoch from now()) / 300)::integer, v_count);
        v_text := v_arr->>v_index;
        if jsonb_array_length(v_arr_rich) > v_index then
          v_fragments := v_arr_rich->v_index;
        end if;
      end if;
    elsif v_category = 'manual' and array_length(v_manual, 1) is not null then
      v_index := mod(floor(extract(epoch from now()) / 3600)::integer, array_length(v_manual, 1)) + 1;
      v_text := v_manual[v_index];
      if position(' • ' in v_text) > 0 then
        v_fragments := jsonb_build_array(
          jsonb_build_object('text', split_part(v_text, ' • ', 1) || ' • ', 'color', 'FF9F0A'),
          jsonb_build_object('text', substring(v_text from position(' • ' in v_text) + 3), 'color', 'FFFFFF')
        );
      end if;
    end if;

    -- Missing categories gracefully fall back to app-owned automatic content.
    if btrim(coalesce(v_text, '')) = '' then
      v_category := 'fallback';
      v_fragments := null;
      v_text := coalesce(
        nullif(v_payload->>'weekly', ''),
        nullif(v_payload->>'live_games', ''),
        nullif(v_payload->>'readiness', ''),
        'SUNDAY PICK''EM'
      );
    end if;
  end if;

  v_text := left(regexp_replace(coalesce(v_text, ''), E'[\\n\\r\\t]+', ' ', 'g'), 420);
  if v_fragments is not null and jsonb_typeof(v_fragments) = 'array' and jsonb_array_length(v_fragments) = 0 then
    v_fragments := null;
  end if;

  v_event_id := v_week.id::text || ':' || v_slot::text || ':' || v_category;
  return jsonb_build_object(
    'ok', true,
    'active', true,
    'test', false,
    'week', v_week.nfl_week,
    'event_id', v_event_id,
    'category', v_category,
    'text', v_text,
    'fragments', v_fragments,
    'color', v_color
  );
end;
$$;

commit;
notify pgrst, 'reload schema';
