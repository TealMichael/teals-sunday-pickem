-- Teal's Sunday Pick'em — AWTRIX clock RPC repair
-- Records the database fixes proven by physical-clock diagnostics.
-- Safe/idempotent: no scoring, picks, lineups, or player-pool data changes.

alter function pickem.clock_feed(text)
set search_path = pickem, public, extensions, pg_temp;

alter function pickem.clock_ack(text, text)
set search_path = pickem, public, extensions, pg_temp;

create or replace function public.pickem_clock_feed(p_token text)
returns jsonb
language sql
security definer
set search_path = public, pickem, extensions, pg_temp
as $$
  select pickem.clock_feed(p_token);
$$;

create or replace function public.pickem_clock_ack(p_token text, p_event_id text)
returns jsonb
language sql
security definer
set search_path = public, pickem, extensions, pg_temp
as $$
  select pickem.clock_ack(p_token, p_event_id);
$$;

revoke all on function public.pickem_clock_feed(text) from public;
revoke all on function public.pickem_clock_ack(text, text) from public;
grant execute on function public.pickem_clock_feed(text) to anon, authenticated;
grant execute on function public.pickem_clock_ack(text, text) to anon, authenticated;

notify pgrst, 'reload schema';
