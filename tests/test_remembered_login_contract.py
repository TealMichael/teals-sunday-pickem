from pathlib import Path


def _app_text() -> str:
    return Path(__file__).parents[1].joinpath("app.py").read_text("utf-8")


def test_uses_same_first_party_storage_architecture_as_proven_apps():
    app = _app_text()
    assert "st.components.v2.component(" in app
    assert "window.localStorage.setItem" in app
    assert "window.localStorage.getItem" in app
    assert "document.cookie" in app
    assert "st.context.cookies.get(COOKIE_NAME" in app


def test_no_third_party_cookie_manager_remains():
    app = _app_text()
    assert "extra_streamlit_components" not in app
    assert "CookieManager" not in app
    requirements = Path(__file__).parents[1].joinpath("requirements.txt").read_text("utf-8")
    assert "extra-streamlit-components" not in requirements


def test_restore_waits_for_localstorage_before_giving_up():
    app = _app_text()
    assert "if not cookie_token and not storage_ready:" in app
    assert "return" in app
    assert "_restore_remembered_cookie_fast_path" in app
    assert "_restore_remembered_player" in app


def test_manual_login_queues_first_party_browser_storage():
    app = _app_text()
    assert "_queue_remember_cookie_set(result.cookie_value)" in app
    assert "_queue_remember_storage_set(token)" in app
    assert "active_device_token" in app
    assert "document.cookie" in app


def test_signout_revokes_and_clears_browser_storage():
    app = _app_text()
    assert "revoke_cookie_session(store, token)" in app
    assert "_queue_remember_cookie_delete()" in app
    assert "window.localStorage.removeItem" in app
