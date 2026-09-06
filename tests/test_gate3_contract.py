from pathlib import Path


def test_gate3_migration_isolated_and_server_only():
    text = Path("db/003_gate3_nfl_data.sql").read_text()
    for table in ("nfl_games", "nfl_players", "player_week_stats", "data_runs"):
        assert f"pickem.{table}" in text
        assert f"grant all on table pickem.{table} to service_role" in text
        assert f"revoke all on table pickem.{table} from anon, authenticated" in text
    assert "drop schema" not in text.lower()
    assert "public.players" not in text


def test_scheduler_is_30_minute_and_has_manual_dispatch():
    text = Path(".github/workflows/nfl-refresh.yml").read_text()
    assert 'cron: "*/30 0,7-23 * * *"' in text
    assert 'timezone: "America/New_York"' in text
    assert "workflow_dispatch:" in text
    assert "SUPABASE_SECRET_KEY" in text


def test_gate3_has_replaceable_provider_layer_and_no_paid_api_dependency():
    sources = Path("nfl_sources.py").read_text()
    assert "class ESPNProvider" in sources
    assert "class SleeperProvider" in sources
    assert "class NFLverseProvider" in sources
    combined = "\n".join(p.read_text() for p in [Path("nfl_sources.py"), Path("nfl_sync.py"), Path("nfl_rankings.py")])
    assert "sportsdataio" not in combined.lower()
    assert "fantasypros.com" not in combined.lower()
    assert "nfl logo" not in combined.lower()


def test_kicker_rule_documented_in_code_is_flat_three():
    text = Path("nfl_scoring.py").read_text()
    assert "fg_made * 3.0" in text
    assert "regardless of distance" in text
