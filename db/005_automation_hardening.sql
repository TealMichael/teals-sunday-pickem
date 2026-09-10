-- Teal's Sunday Pick'em v1.0.6 — Automation Hardening
-- Run after 004_gate4_live_social.sql.
-- This adds only a server-side lease table used to prevent duplicate
-- Streamlit fallback refreshes when GitHub Actions is delayed.

create table if not exists pickem.refresh_leases (
  lease_key text primary key,
  owner text not null,
  claimed_at timestamptz not null default now(),
  expires_at timestamptz not null
);

create index if not exists refresh_leases_expires_idx on pickem.refresh_leases(expires_at);

alter table pickem.refresh_leases enable row level security;
revoke all on table pickem.refresh_leases from anon, authenticated;
grant all on table pickem.refresh_leases to service_role;

insert into pickem.app_meta(key, value)
values ('schema_version', '{"version":"1.0.6"}'::jsonb)
on conflict (key) do update set value=excluded.value, updated_at=now();
