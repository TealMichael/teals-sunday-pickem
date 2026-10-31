-- Preferred rollback: retain v1.0.15 code and data protections.
-- Fences in-flight candidates; future page refreshes use coordinated sync mode.
select pickem.refresh_set_background(false);
select protocol,background_enabled from pickem.refresh_control;
