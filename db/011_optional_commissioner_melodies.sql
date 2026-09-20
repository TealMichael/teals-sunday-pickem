-- Teal's Sunday Pick'em v1.0.7-hotfix7.16
-- OPTIONAL Commissioner-message melody. Run ONCE (safe to rerun) after
-- db/007_awtrix_clock_rpc_hotfix.sql and db/010_clock_rich_fragment_render_fix.sql.
--
-- Does NOT modify pickem.clock_feed, its cadence, clock snapshots, scoring,
-- lineups, tokens, or the separate Class Schedule / Daily Fact Challenge clock.
-- Only enhances the existing public feed wrapper after the ORIGINAL private
-- function has produced and authenticated the normal display message.
-- When disabled, unconfigured, or on any optional lookup error the wrapper
-- returns the original JSON unchanged.

begin;

create table if not exists pickem.clock_message_melodies (
  week_id uuid primary key references pickem.weeks(id) on delete cascade,
  enabled boolean not null default false,
  target text not null default 'welcome'
    check (target in ('welcome', 'party', 'custom')),
  tune text not null default 'happy_birthday'
    check (tune in ('happy_birthday', 'jingle_bells', 'twinkle_twinkle', 'ode_to_joy', 'celebration_chime')),
  updated_at timestamptz not null default now()
);

alter table pickem.clock_message_melodies enable row level security;
revoke all on table pickem.clock_message_melodies from public, anon, authenticated;
grant all on table pickem.clock_message_melodies to service_role;

-- Preserve the exact established token validation, test behavior, five-minute
-- category rotation, text, rich colors, and event IDs by CALLING the existing
-- private function rather than copying/replacing its substantial logic.
create or replace function public.pickem_clock_feed(p_token text)
returns jsonb
language plpgsql
security definer
set search_path = public, pickem, extensions, pg_temp
as $$
declare
  v_feed jsonb;
  v_week text;
  v_target text := '';
  v_tune text;
  v_rtttl text;
  v_text text;
begin
  v_feed := pickem.clock_feed(p_token);
  if v_feed is null
     or coalesce(v_feed->>'ok', '') <> 'true'
     or coalesce(v_feed->>'active', '') <> 'true'
     or coalesce(v_feed->>'test', '') = 'true'
     or coalesce(v_feed->>'category', '') <> 'manual' then
    return v_feed;
  end if;

  v_text := coalesce(v_feed->>'text', '');
  if left(v_text, length('WELCOME • ')) = 'WELCOME • ' then
    v_target := 'welcome';
  elsif left(v_text, length('SUNDAY AT TEAL''S • ')) = 'SUNDAY AT TEAL''S • ' then
    v_target := 'party';
  elsif left(v_text, length('FROM THE COMMISH • ')) = 'FROM THE COMMISH • ' then
    v_target := 'custom';
  else
    return v_feed;
  end if;

  -- event_id starts with the week UUID, followed by :slot:manual. Never
  -- cast untrusted strings without validating their shape first.
  v_week := split_part(coalesce(v_feed->>'event_id', ''), ':', 1);
  if v_week !~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' then
    return v_feed;
  end if;

  begin
    select m.tune into v_tune
      from pickem.clock_message_melodies as m
      join pickem.clock_week_settings as s on s.week_id = m.week_id
      where m.week_id = v_week::uuid
        and m.enabled = true
        and m.target = v_target
        and (
          (v_target = 'welcome' and s.welcome_enabled and btrim(s.welcome_text) <> '')
          or (v_target = 'party' and s.party_enabled and btrim(s.party_text) <> '')
          or (v_target = 'custom' and s.custom_enabled and btrim(s.custom_text) <> '')
        )
      limit 1;
  exception when others then
    -- A music-only failure must never prevent the established ticker feed.
    return v_feed;
  end;

  -- Static, allowlisted, monophonic RTTTL; no custom audio or arbitrary input.
  -- The inline sound accompanies each occurrence of the chosen manual message.
  v_rtttl := case v_tune
    when 'happy_birthday' then
      'HappyBday:d=4,o=5,b=125:8c.,16c,d,c,f,2e,8c.,16c,d,c,g,2f,8c.,16c,c6,a,f,e,d,8a#.,16a#,a,f,g,2f'
    when 'jingle_bells' then
      'JingleBell:d=4,o=5,b=170:b,b,b,8p,b,b,b,8p,b,d6,g.,8a,2b'
    when 'twinkle_twinkle' then
      'Twinkle:d=4,o=5,b=140:c,c,g,g,a,a,2g,f,f,e,e,d,d,2c'
    when 'ode_to_joy' then
      'OdeToJoy:d=4,o=5,b=140:e,e,f,g,g,f,e,d,c,c,d,e,2e,2d'
    when 'celebration_chime' then
      'Celebrate:d=8,o=5,b=180:c,e,g,c6,4p,4g,2c6'
    else null
  end;

  if v_rtttl is null then
    return v_feed;
  end if;
  return v_feed || jsonb_build_object('rtttl', v_rtttl);
end;
$$;

revoke all on function public.pickem_clock_feed(text) from public;
grant execute on function public.pickem_clock_feed(text) to anon, authenticated;

commit;
notify pgrst, 'reload schema';
