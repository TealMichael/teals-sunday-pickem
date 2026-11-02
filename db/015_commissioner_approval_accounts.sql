-- Teal's Sunday Pick'em v1.0.16 — Commissioner-only account approval and safe removal
-- RUN ONCE in the existing shared Supabase project, SQL Editor, BEFORE deploying app v1.0.16.
-- Changes ONLY pickem schema. Existing accounts stay approved. New accounts begin pending.
-- This migration does NOT remove any existing accounts.

begin;

alter table pickem.players
  add column if not exists account_status text not null default 'approved';
alter table pickem.players
  alter column account_status set default 'pending';
alter table pickem.players
  add column if not exists approved_at timestamptz;

-- Existing players, including the two unknown accounts, retain their current
-- active state until the Commissioner explicitly removes them.
-- Only new registrations after this migration enter the pending queue.

alter table pickem.players
  drop constraint if exists players_account_status_check;
alter table pickem.players
  add constraint players_account_status_check
  check (account_status in ('pending', 'approved', 'disabled'));

create index if not exists players_account_status_created_idx
  on pickem.players (account_status, created_at);

-- Small global burst guard for the private family game. Only pending requests
-- are counted. Serialize signup inserts so simultaneous requests can't defeat
-- the limits. Does not affect weekly scoring, NFL refresh or existing logins.
create or replace function pickem.limit_pending_registration()
returns trigger language plpgsql
set search_path = pickem, pg_temp
as $$
begin
  if new.account_status = 'pending' then
    perform pg_advisory_xact_lock(251016, 1);
    if (select count(*) from pickem.players where account_status = 'pending') >= 12 then
      raise exception 'Too many pending requests. Ask the Commissioner to review them.' using errcode = 'P0001';
    end if;
    if (select count(*) from pickem.players
        where account_status = 'pending' and created_at > now() - interval '1 hour') >= 8 then
      raise exception 'New player requests are temporarily limited. Please try again later.' using errcode = 'P0001';
    end if;
  end if;
  return new;
end;
$$;

drop trigger if exists players_limit_pending_registration on pickem.players;
create trigger players_limit_pending_registration
  before insert on pickem.players
  for each row execute function pickem.limit_pending_registration();

-- Atomic safe removal. If any lineup or archived result exists, keep the
-- identity (and history) but disable login. Otherwise delete the account;
-- remembered device rows are removed via existing FK cascade.
-- All outcomes revoke remembered sessions, including for disabled users.
-- No caller can hard-delete the owner, even if the UI accidentally offers it.
create or replace function pickem.commissioner_remove_account(p_player_id uuid)
returns text
language plpgsql
set search_path = pickem, pg_temp
as $$
declare
  target pickem.players%rowtype;
  linked_owner text;
  preserve_history boolean;
begin
  select * into target from pickem.players where id = p_player_id for update;
  if not found then
    raise exception 'Player not found.' using errcode = 'P0001';
  end if;

  select value->>'player_id' into linked_owner
    from pickem.app_meta where key = 'commissioner_owner:v1';
  if lower(trim(target.nickname)) = 'mike t.'
      or target.id::text = coalesce(linked_owner, '') then
    raise exception 'The Commissioner account cannot be removed.' using errcode = 'P0001';
  end if;

  select
    exists(select 1 from pickem.lineups where player_id = p_player_id)
    or exists(select 1 from pickem.weekly_results where player_id = p_player_id)
    or exists(select 1 from pickem.season_champions where player_id = p_player_id)
    or exists(select 1 from pickem.app_meta
              where key like ('pickem_pulse_reaction:%:' || p_player_id::text)
                 or value::text like ('%' || p_player_id::text || '%'))
    into preserve_history;

  if preserve_history then
    update pickem.players set account_status = 'disabled' where id = p_player_id;
    update pickem.player_sessions set revoked_at = now()
      where player_id = p_player_id and revoked_at is null;
    return 'disabled';
  end if;

  delete from pickem.players where id = p_player_id;
  return 'deleted';
end;
$$;

revoke all on function pickem.commissioner_remove_account(uuid) from public, anon, authenticated;
grant execute on function pickem.commissioner_remove_account(uuid) to service_role;
revoke all on function pickem.limit_pending_registration() from public, anon, authenticated;

-- Refresh the PostgREST schema cache for the new column and function.
notify pgrst, 'reload schema';

commit;
