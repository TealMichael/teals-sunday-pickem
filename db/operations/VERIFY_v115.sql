-- Read-only installation/rollback-mode verification. Contains no owner tokens.
select protocol, background_enabled from pickem.refresh_control;
select
 has_function_privilege('service_role', 'pickem.refresh_claim(uuid,text,boolean)', 'EXECUTE') as server_can_claim,
 has_function_privilege('anon', 'pickem.refresh_claim(uuid,text,boolean)', 'EXECUTE') as anonymous_can_claim,
 has_function_privilege('authenticated', 'pickem.refresh_commit(jsonb,jsonb)', 'EXECUTE') as browser_can_commit;
select count(*) as installed_statement_guards
from pg_trigger t join pg_class c on c.oid=t.tgrelid join pg_namespace n on n.oid=c.relnamespace
where n.nspname='pickem' and t.tgname='refresh_lock_before' and not t.tgisinternal;
select w.season,w.nfl_week,w.data_status,w.last_data_refresh_at,
 pickem.refresh_read_week(w.id)->>'refresh_status' as refresh_status,
 pickem.refresh_read_week(w.id)->>'archive_pending' as archive_pending
from pickem.weeks w where not w.is_demo order by w.season desc,w.nfl_week desc limit 3;
