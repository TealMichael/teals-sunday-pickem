from pathlib import Path


def test_store_cache_is_version_keyed():
    text = Path("app.py").read_text()
    assert "def get_store(url: str, service_key: str, build_version: str)" in text
    assert "get_store(secret(\"SUPABASE_URL\"), supabase_server_key(), APP_BUILD_VERSION)" in text


def test_onboarding_uses_native_bordered_cards():
    text = Path("weekly_ui.py").read_text()
    assert text.count("with st.container(border=True):") >= 3
    assert "1 · Pick your five." in text
    assert "2 · Know the scoring." in text
    assert "3 · Questionable player? Set a backup." in text
