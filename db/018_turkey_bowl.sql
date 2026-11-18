-- Teal's Sunday Pick'em v1.0.19 — isolated Turkey Bowl special event.
-- Run ONCE in the EXISTING shared Supabase project, before uploading the app.
-- Additive only; never modifies regular Sunday weeks, picks, pool, or scoring triggers.
BEGIN;

CREATE TABLE IF NOT EXISTS pickem.special_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  event_type text NOT NULL CHECK (event_type = 'turkey_bowl'),
  season integer NOT NULL CHECK (season BETWEEN 2026 AND 2100),
  nfl_week integer NOT NULL CHECK (nfl_week BETWEEN 1 AND 18),
  game_date date NOT NULL,
  opens_at timestamptz NOT NULL,
  locks_at timestamptz NOT NULL,
  published_at timestamptz,
  finalized_at timestamptz,
  refreshed_at timestamptz,
  UNIQUE (event_type, season),
  CHECK (locks_at > opens_at)
);

CREATE TABLE IF NOT EXISTS pickem.special_games (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id uuid NOT NULL REFERENCES pickem.special_events(id) ON DELETE CASCADE,
  provider_event_id text NOT NULL,
  home_team text NOT NULL,
  away_team text NOT NULL,
  kickoff_at timestamptz NOT NULL,
  game_status text NOT NULL DEFAULT 'SCHEDULED' CHECK (game_status IN ('SCHEDULED','LIVE','FINAL','POSTPONED','CANCELED')),
  completed boolean NOT NULL DEFAULT false,
  home_score integer,
  away_score integer,
  period integer,
  game_clock text,
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (event_id, provider_event_id)
);

CREATE TABLE IF NOT EXISTS pickem.special_pool (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id uuid NOT NULL REFERENCES pickem.special_events(id) ON DELETE CASCADE,
  position text NOT NULL CHECK (position IN ('QB','RB','WR','TE','K')),
  slot_rank integer NOT NULL CHECK (slot_rank BETWEEN 1 AND 16),
  player_name text NOT NULL,
  sleeper_player_id text,
  team_abbr text NOT NULL,
  opponent_abbr text NOT NULL,
  kickoff_at timestamptz NOT NULL,
  is_visible boolean NOT NULL DEFAULT false,
  availability_status text NOT NULL DEFAULT 'HEALTHY' CHECK (availability_status IN ('HEALTHY','QUESTIONABLE','OUT')),
  raw_injury_status text,
  score_total numeric(8,3) NOT NULL DEFAULT 0,
  score_breakdown jsonb NOT NULL DEFAULT '{}'::jsonb,
  score_status text NOT NULL DEFAULT 'SCHEDULED' CHECK (score_status IN ('SCHEDULED','LIVE','FINAL')),
  score_updated_at timestamptz,
  manual_score_override numeric(8,3),
  manual_override_note text,
  UNIQUE (event_id, position, slot_rank)
);

CREATE TABLE IF NOT EXISTS pickem.special_lineups (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id uuid NOT NULL REFERENCES pickem.special_events(id) ON DELETE CASCADE,
  player_id uuid NOT NULL REFERENCES pickem.players(id),
  confirmed_at timestamptz,
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (event_id, player_id)
);

CREATE TABLE IF NOT EXISTS pickem.special_picks (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  lineup_id uuid NOT NULL REFERENCES pickem.special_lineups(id) ON DELETE CASCADE,
  position text NOT NULL CHECK (position IN ('QB','RB','WR','TE','K')),
  pool_player_id uuid NOT NULL REFERENCES pickem.special_pool(id),
  emergency_pool_player_id uuid REFERENCES pickem.special_pool(id),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (lineup_id, position),
  CHECK (emergency_pool_player_id IS NULL OR emergency_pool_player_id <> pool_player_id)
);

CREATE TABLE IF NOT EXISTS pickem.special_results (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id uuid NOT NULL REFERENCES pickem.special_events(id) ON DELETE CASCADE,
  season integer NOT NULL,
  nfl_week integer NOT NULL,
  player_id uuid NOT NULL REFERENCES pickem.players(id),
  nickname_snapshot text NOT NULL,
  emoji_snapshot text NOT NULL,
  weekly_score numeric(9,3) NOT NULL,
  finish_rank integer NOT NULL,
  season_points integer NOT NULL,
  is_champion boolean NOT NULL,
  finalized_at timestamptz NOT NULL,
  UNIQUE (event_id, player_id)
);

CREATE INDEX IF NOT EXISTS special_games_event_idx ON pickem.special_games(event_id);
CREATE INDEX IF NOT EXISTS special_pool_event_idx ON pickem.special_pool(event_id, position, slot_rank);
CREATE INDEX IF NOT EXISTS special_lineups_event_idx ON pickem.special_lineups(event_id);
CREATE INDEX IF NOT EXISTS special_results_season_idx ON pickem.special_results(season, event_id);

-- The Streamlit app's service role reads these data; browser credentials never do.
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['special_events','special_games','special_pool','special_lineups','special_picks','special_results'] LOOP
    EXECUTE format('ALTER TABLE pickem.%I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('REVOKE ALL ON TABLE pickem.%I FROM anon, authenticated', t);
    EXECUTE format('GRANT ALL ON TABLE pickem.%I TO service_role', t);
  END LOOP;
END $$;

-- Enforce event opening, published pool, approved account and Thursday lock at
-- the database layer, not the browser clock. Covers lineups AND picks, including
-- deletes and confirmation updates. Guards apply even with service-role writes.
CREATE OR REPLACE FUNCTION pickem.guard_special_lineup()
RETURNS trigger LANGUAGE plpgsql SET search_path=pickem,pg_temp AS $$
DECLARE ev pickem.special_events%rowtype;
  status text;
BEGIN
  IF TG_OP='DELETE' THEN
    SELECT * INTO ev FROM pickem.special_events WHERE id=OLD.event_id;
  ELSE
    SELECT * INTO ev FROM pickem.special_events WHERE id=NEW.event_id;
  END IF;
  IF ev.id IS NULL OR now() < ev.opens_at OR now() >= ev.locks_at OR ev.published_at IS NULL THEN
    RAISE EXCEPTION 'Turkey Bowl lineups are not open.' USING errcode='P0001';
  END IF;
  IF TG_OP <> 'DELETE' THEN
    SELECT account_status INTO status FROM pickem.players WHERE id=NEW.player_id;
    IF status IS DISTINCT FROM 'approved' THEN
      RAISE EXCEPTION 'Player is not approved.' USING errcode='P0001';
    END IF;
    IF TG_OP='UPDATE' AND (NEW.event_id<>OLD.event_id OR NEW.player_id<>OLD.player_id) THEN
      RAISE EXCEPTION 'Lineup ownership cannot change.' USING errcode='P0001';
    END IF;
    NEW.updated_at=now();
    RETURN NEW;
  END IF;
  RETURN OLD;
END $$;

DROP TRIGGER IF EXISTS trg_guard_special_lineup ON pickem.special_lineups;
CREATE TRIGGER trg_guard_special_lineup BEFORE INSERT OR UPDATE OR DELETE ON pickem.special_lineups
FOR EACH ROW EXECUTE FUNCTION pickem.guard_special_lineup();

CREATE OR REPLACE FUNCTION pickem.guard_special_pick()
RETURNS trigger LANGUAGE plpgsql SET search_path=pickem,pg_temp AS $$
DECLARE lineup pickem.special_lineups%rowtype;
  ev pickem.special_events%rowtype;
  starter pickem.special_pool%rowtype;
  backup pickem.special_pool%rowtype;
BEGIN
  IF TG_OP='DELETE' THEN
    SELECT * INTO lineup FROM pickem.special_lineups WHERE id=OLD.lineup_id;
  ELSE
    SELECT * INTO lineup FROM pickem.special_lineups WHERE id=NEW.lineup_id;
  END IF;
  SELECT * INTO ev FROM pickem.special_events WHERE id=lineup.event_id;
  IF ev.id IS NULL OR ev.published_at IS NULL OR now() < ev.opens_at OR now() >= ev.locks_at THEN
    RAISE EXCEPTION 'Turkey Bowl picks are locked or unavailable.' USING errcode='P0001';
  END IF;
  IF TG_OP='DELETE' THEN RETURN OLD; END IF;
  IF TG_OP='UPDATE' AND NEW.lineup_id<>OLD.lineup_id THEN
    RAISE EXCEPTION 'Cannot move a pick between lineups.' USING errcode='P0001';
  END IF;
  SELECT * INTO starter FROM pickem.special_pool WHERE id=NEW.pool_player_id;
  IF starter.id IS NULL OR starter.event_id<>ev.id OR starter.position<>NEW.position
       OR NOT starter.is_visible OR starter.availability_status='OUT' THEN
    RAISE EXCEPTION 'Starter is not available in this position.' USING errcode='P0001';
  END IF;
  IF NEW.emergency_pool_player_id IS NOT NULL THEN
    SELECT * INTO backup FROM pickem.special_pool WHERE id=NEW.emergency_pool_player_id;
    IF backup.id IS NULL OR backup.event_id<>ev.id OR backup.position<>NEW.position
         OR NOT backup.is_visible OR backup.availability_status='OUT' OR backup.id=starter.id THEN
      RAISE EXCEPTION 'Emergency backup is not available in this position.' USING errcode='P0001';
    END IF;
  END IF;
  NEW.updated_at=now();
  RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS trg_guard_special_pick ON pickem.special_picks;
CREATE TRIGGER trg_guard_special_pick BEFORE INSERT OR UPDATE OR DELETE ON pickem.special_picks
FOR EACH ROW EXECUTE FUNCTION pickem.guard_special_pick();

-- Atomic Commissioner-only reserve promotion; never moves or deletes a pick.
CREATE OR REPLACE FUNCTION pickem.promote_special_reserve(
  p_event_id uuid, p_outgoing uuid, p_incoming uuid
) RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path=pickem,pg_temp AS $$
DECLARE ev pickem.special_events%rowtype;
  old_row pickem.special_pool%rowtype;
  new_row pickem.special_pool%rowtype;
BEGIN
  SELECT * INTO ev FROM pickem.special_events WHERE id=p_event_id FOR UPDATE;
  IF ev.id IS NULL OR ev.published_at IS NULL OR now() >= ev.locks_at OR now() < ev.opens_at THEN
    RAISE EXCEPTION 'Pool promotions are closed.' USING errcode='P0001';
  END IF;
  SELECT * INTO old_row FROM pickem.special_pool WHERE id=p_outgoing FOR UPDATE;
  SELECT * INTO new_row FROM pickem.special_pool WHERE id=p_incoming FOR UPDATE;
  IF old_row.event_id IS DISTINCT FROM ev.id OR new_row.event_id IS DISTINCT FROM ev.id
     OR old_row.position IS DISTINCT FROM new_row.position
     OR NOT old_row.is_visible OR new_row.is_visible OR new_row.availability_status='OUT' THEN
    RAISE EXCEPTION 'Invalid special-event reserve promotion.' USING errcode='P0001';
  END IF;
  UPDATE pickem.special_pool SET is_visible=false WHERE id=p_outgoing;
  UPDATE pickem.special_pool SET is_visible=true WHERE id=p_incoming;
END $$;
REVOKE ALL ON FUNCTION pickem.promote_special_reserve(uuid,uuid,uuid) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION pickem.promote_special_reserve(uuid,uuid,uuid) TO service_role;

-- Existing account-removal feature must now preserve special-event histories,
-- just as it already preserves Sunday lineups and season champions. Keep the
-- original owner protection, PIN session revocation, and return contract.
CREATE OR REPLACE FUNCTION pickem.commissioner_remove_account(p_player_id uuid)
RETURNS text LANGUAGE plpgsql SET search_path=pickem,pg_temp AS $$
DECLARE target pickem.players%rowtype;
  linked_owner text;
  preserve_history boolean;
BEGIN
  SELECT * INTO target FROM pickem.players WHERE id=p_player_id FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Player not found.' USING errcode='P0001';
  END IF;
  SELECT value->>'player_id' INTO linked_owner
    FROM pickem.app_meta WHERE key='commissioner_owner:v1';
  IF lower(trim(target.nickname))='mike t.' OR target.id::text=coalesce(linked_owner,'') THEN
    RAISE EXCEPTION 'The Commissioner account cannot be removed.' USING errcode='P0001';
  END IF;
  SELECT
    exists(SELECT 1 FROM pickem.lineups WHERE player_id=p_player_id)
    OR exists(SELECT 1 FROM pickem.weekly_results WHERE player_id=p_player_id)
    OR exists(SELECT 1 FROM pickem.season_champions WHERE player_id=p_player_id)
    OR exists(SELECT 1 FROM pickem.special_lineups WHERE player_id=p_player_id)
    OR exists(SELECT 1 FROM pickem.special_results WHERE player_id=p_player_id)
    OR exists(SELECT 1 FROM pickem.app_meta
        WHERE key LIKE ('pickem_pulse_reaction:%:' || p_player_id::text)
           OR value::text LIKE ('%' || p_player_id::text || '%'))
    INTO preserve_history;
  IF preserve_history THEN
    UPDATE pickem.players SET account_status='disabled' WHERE id=p_player_id;
    UPDATE pickem.player_sessions SET revoked_at=now()
      WHERE player_id=p_player_id AND revoked_at IS NULL;
    RETURN 'disabled';
  END IF;
  DELETE FROM pickem.players WHERE id=p_player_id;
  RETURN 'deleted';
END $$;
REVOKE ALL ON FUNCTION pickem.commissioner_remove_account(uuid) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION pickem.commissioner_remove_account(uuid) TO service_role;

-- 2026 only: annual support uses a new event row each year, never duplicates.
INSERT INTO pickem.special_events(event_type,season,nfl_week,game_date,opens_at,locks_at)
VALUES ('turkey_bowl',2026,12,'2026-11-26','2026-11-24 12:00:00-05','2026-11-26 13:00:00-05')
ON CONFLICT (event_type,season) DO NOTHING;

NOTIFY pgrst,'reload schema';
COMMIT;
