from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_hotfix791_forces_store_and_commissioner_ui_reload_on_warm_worker():
    config = (ROOT / "config.py").read_text("utf-8")
    app = (ROOT / "app.py").read_text("utf-8")
    store = (ROOT / "store.py").read_text("utf-8")
    ui = (ROOT / "gate5_ui.py").read_text("utf-8")

    assert 'APP_BUILD_VERSION = "1.0.7-hotfix7.9.1"' in config
    assert 'STORE_SCHEMA_VERSION = 4' in store
    assert 'GATE5_UI_SCHEMA_VERSION = 6' in ui
    assert 'getattr(_store, "STORE_SCHEMA_VERSION", 0) < 4' in app
    assert 'not hasattr(_store.SupabaseStore, "get_app_meta")' in app
    assert 'not hasattr(_store.SupabaseStore, "set_app_meta")' in app
    assert 'getattr(_gate5_ui, "GATE5_UI_SCHEMA_VERSION", 0) < 6' in app


def test_newsletter_settings_failure_cannot_hide_final_recap():
    ui = (ROOT / "gate5_ui.py").read_text("utf-8")
    # Settings persistence is optional. A stale worker or transient app_meta read
    # must fall back to an empty setting rather than throwing the whole Newsletter
    # tab into the generic runtime-error screen.
    assert 'getter = getattr(store, "get_app_meta", None)' in ui
    assert 'if callable(getter):' in ui
    assert 'except Exception:' in ui
    assert 'meta = {}' in ui
    assert 'setter = getattr(store, "set_app_meta", None)' in ui
    assert 'The newsletter preview is still safe to use.' in ui
