-- EMERGENCY FULL ROLLBACK ONLY. See START_HERE_v115.md.
-- Stop the Streamlit app and all scheduled/manual jobs FIRST; confirm stopped.
-- Normal fallback is simply select pickem.refresh_set_background(false);
-- This script keeps scores, lineups, histories, accounts, and coordinator tables.
begin;
set local lock_timeout='10s';
select pickem.refresh_set_background(false);
do $$ declare r record;t text;begin
 for r in select p.oid::regprocedure as sig from pg_proc p join pg_namespace n on n.oid=p.pronamespace
 where n.nspname='pickem' and p.proname in ('refresh_claim','refresh_release','refresh_read_week','refresh_revision','refresh_set_background','refresh_edit','refresh_commit','refresh_override','refresh_archive','refresh_purge','refresh_pending_archives') loop
  execute format('revoke all on function %s from public,anon,authenticated,service_role',r.sig);
 end loop;
 foreach t in array array['weeks','nfl_games','player_pool','player_week_stats','weekly_results','season_champions','clock_snapshots','lineups','lineup_picks','players'] loop
  execute format('drop trigger if exists refresh_lock_before on pickem.%I',t);
  execute format('drop trigger if exists refresh_revision_after on pickem.%I',t);
 end loop;
end $$;
notify pgrst,'reload schema';
commit;
