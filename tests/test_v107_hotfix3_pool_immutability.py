import inspect
from pathlib import Path

from nfl_sync import publish_week_pool
from store import SupabaseStore
from weekly import selected_pool_ids_missing_from_visible_pool


class NoPublishStore:
    def start_data_run(self, *args, **kwargs):
        raise AssertionError("published pool should return before any data run starts")


def test_publish_retry_is_a_noop_once_week_is_published():
    result = publish_week_pool(NoPublishStore(), {"id": "w1", "published_at": "2026-09-08T16:00:00+00:00"})
    assert result["published"] is False
    assert "frozen" in result["message"].lower()


def test_automatic_out_replacement_never_deletes_saved_starter_or_unconfirms_lineup():
    source = inspect.getsource(SupabaseStore.promote_replacements_for_out_players)
    assert '.delete().eq("pool_player_id"' not in source
    assert '"confirmed_at": None' not in source
    assert "preserved_starters" in source


def test_schedule_replacement_never_deletes_saved_starter_or_unconfirms_lineup():
    source = inspect.getsource(SupabaseStore.reconcile_pool_schedule)
    assert '.delete().eq("pool_player_id"' not in source
    assert '"confirmed_at": None' not in source
    assert "preserved_starters" in source


def test_commissioner_pool_override_preserves_existing_starters():
    source = inspect.getsource(SupabaseStore.replace_visible_pool_player)
    assert '.delete().eq("pool_player_id"' not in source
    assert '"confirmed_at": None' not in source
    assert "preserved_starters" in source


def test_hidden_selected_ids_are_detected_without_reopening_visible_pool():
    visible = [{"id": "new-te", "position": "TE", "is_visible": True}]
    picks = [{"position": "TE", "pool_player_id": "old-te", "emergency_pool_player_id": None}]
    assert selected_pool_ids_missing_from_visible_pool(visible, picks) == ["old-te"]


def test_player_ui_hydrates_preserved_hidden_rows_for_display_only():
    source = Path("weekly_ui.py").read_text(encoding="utf-8")
    assert "get_pool_rows_by_ids" in source
    assert "selected_pool_ids_missing_from_visible_pool" in source
    assert "position_pool(pool, position)" in source  # selection list remains visible-only by default
