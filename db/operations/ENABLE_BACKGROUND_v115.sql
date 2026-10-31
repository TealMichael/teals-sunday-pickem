-- Run only after the v1.0.15 app AND scheduled code are installed and verified.
select pickem.refresh_set_background(true);
select protocol,background_enabled from pickem.refresh_control;
