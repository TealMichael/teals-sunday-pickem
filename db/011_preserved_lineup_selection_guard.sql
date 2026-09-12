-- Teal's Sunday Pick'em v1.0.7-hotfix7.2
-- Final Sunday Freeze Hardening
--
-- Hotfix 3 intentionally preserves an already-saved starter when a published
-- pool option is later hidden because of injury, schedule, or commissioner
-- replacement. The original Gate 2 trigger predates that rule and revalidated
-- starter visibility on every UPDATE, which could block a harmless background
-- cleanup that only clears an invalid emergency backup.
--
-- This replacement keeps the universal lock/open checks intact, preserves the
-- week/position membership guard, validates schedule eligibility for every new
-- starter/backup selection, and permits exactly one historical-lineup cleanup:
-- clearing an emergency backup while leaving the preserved starter unchanged.

create or replace function pickem.guard_lineup_pick()
returns trigger
language plpgsql
set search_path = pickem, public, pg_temp
as $$
declare
  v_lineup_id uuid;
  v_lineup pickem.lineups%rowtype;
  v_week pickem.weeks%rowtype;
  v_starter pickem.player_pool%rowtype;
  v_backup pickem.player_pool%rowtype;
  v_cleanup_only boolean := false;
begin
  if tg_op = 'DELETE' then
    v_lineup_id := old.lineup_id;
  else
    v_lineup_id := new.lineup_id;
  end if;

  select * into v_lineup from pickem.lineups where id = v_lineup_id;
  select * into v_week from pickem.weeks where id = v_lineup.week_id;

  if now() < v_week.opens_at and not v_week.is_demo then
    raise exception 'Picks are not open yet.' using errcode = 'P0001';
  end if;

  if now() >= v_week.locks_at then
    raise exception 'Picks are locked for this week.' using errcode = 'P0001';
  end if;

  if tg_op <> 'DELETE' then
    select * into v_starter from pickem.player_pool where id = new.pool_player_id;
    if v_starter.id is null
       or v_starter.week_id <> v_lineup.week_id
       or v_starter.position <> new.position then
      raise exception 'Starter does not belong to this weekly position pool.' using errcode = 'P0001';
    end if;

    -- Background replacement workflows may need to clear a now-invalid backup
    -- from a lineup whose starter was already preserved/hidden by an earlier
    -- pool change. No starter, position, or replacement choice changes here.
    if tg_op = 'UPDATE' then
      v_cleanup_only := new.pool_player_id is not distinct from old.pool_player_id
        and new.position is not distinct from old.position
        and old.emergency_pool_player_id is not null
        and new.emergency_pool_player_id is null;
    end if;

    if not v_cleanup_only then
      if not v_starter.is_visible then
        raise exception 'Starter is no longer available in the weekly pool.' using errcode = 'P0001';
      end if;
      if v_starter.availability_status = 'OUT' then
        raise exception 'OUT players cannot be selected.' using errcode = 'P0001';
      end if;
      if not coalesce(v_starter.schedule_eligible, true) then
        raise exception 'Starter no longer has an eligible Sunday game.' using errcode = 'P0001';
      end if;
    end if;

    if new.emergency_pool_player_id is not null then
      select * into v_backup from pickem.player_pool where id = new.emergency_pool_player_id;
      if v_backup.id is null
         or v_backup.week_id <> v_lineup.week_id
         or v_backup.position <> new.position
         or not v_backup.is_visible then
        raise exception 'Emergency backup does not belong to this weekly position pool.' using errcode = 'P0001';
      end if;
      if v_backup.availability_status = 'OUT' then
        raise exception 'OUT players cannot be emergency backups.' using errcode = 'P0001';
      end if;
      if not coalesce(v_backup.schedule_eligible, true) then
        raise exception 'Emergency backup no longer has an eligible Sunday game.' using errcode = 'P0001';
      end if;
    end if;
  end if;

  if tg_op = 'DELETE' then
    return old;
  end if;
  return new;
end;
$$;

notify pgrst, 'reload schema';
