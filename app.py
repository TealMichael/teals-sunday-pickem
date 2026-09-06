from __future__ import annotations

from datetime import datetime, timedelta

import extra_streamlit_components as stx
import streamlit as st

from auth import login_player, register_player, restore_from_cookie, revoke_cookie_session
from config import APP_NAME, COOKIE_NAME, REMEMBER_DAYS
from security import safe_secret_match
from store import SupabaseStore
from ui import foundation_home, hero, inject_css, page_config

page_config()
inject_css()
hero()


def secret(name: str) -> str:
    try:
        return str(st.secrets[name])
    except Exception:
        return ""


@st.cache_resource
def get_store(url: str, service_key: str) -> SupabaseStore:
    return SupabaseStore(url, service_key)


@st.cache_resource
def get_cookie_manager():
    return stx.CookieManager(key="tsp_cookie_manager")


required = ["SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "PIN_PEPPER", "SESSION_PEPPER", "COMMISH_USERNAME", "COMMISH_PIN"]
missing = [name for name in required if not secret(name)]
if missing:
    st.error("App setup is incomplete. Add the required secrets before using Gate 1.")
    with st.expander("Setup details"):
        st.code("Missing: " + ", ".join(missing))
        st.write("Use `.streamlit/secrets.toml.example` as the template. Never commit the real secrets file.")
    st.stop()

store = get_store(secret("SUPABASE_URL"), secret("SUPABASE_SERVICE_ROLE_KEY"))
cookies = get_cookie_manager()

# Rendered shell already exists above. Remembered-login work happens only afterward.
if "player" not in st.session_state:
    st.session_state.player = None
if "commish" not in st.session_state:
    st.session_state.commish = False
if "remember_restore_attempted" not in st.session_state:
    st.session_state.remember_restore_attempted = False

cookie_value = None
try:
    cookie_value = cookies.get(COOKIE_NAME)
except Exception:
    cookie_value = None

if not st.session_state.player and cookie_value and not st.session_state.remember_restore_attempted:
    st.session_state.remember_restore_attempted = True
    result = restore_from_cookie(store, cookie_value, session_pepper=secret("SESSION_PEPPER"))
    if result.ok:
        st.session_state.player = result.player
        st.rerun()
    elif result.message != "TEMPORARY_SESSION_CHECK_FAILURE":
        try:
            cookies.delete(COOKIE_NAME, key="delete_tsp_cookie")
        except Exception:
            pass


def set_remember_cookie(value: str) -> None:
    expires = datetime.now() + timedelta(days=REMEMBER_DAYS)
    cookies.set(
        COOKIE_NAME,
        value,
        expires_at=expires,
        secure=True,
        same_site="lax",
        key="set_tsp_cookie",
    )


def player_login_ui() -> None:
    tab_signin, tab_new = st.tabs(["Sign In", "New Player"])
    with tab_signin:
        with st.form("signin_form"):
            nickname = st.text_input("Nickname", max_chars=15, autocomplete="username")
            pin = st.text_input("4-digit PIN", type="password", max_chars=4, autocomplete="current-password")
            remember = st.checkbox("Keep me signed in this season", value=True)
            submitted = st.form_submit_button("Sign In", type="primary", use_container_width=True)
        if submitted:
            result = login_player(
                store,
                nickname=nickname,
                pin=pin,
                pin_pepper=secret("PIN_PEPPER"),
                session_pepper=secret("SESSION_PEPPER"),
                remember=remember,
            )
            if result.ok:
                st.session_state.player = result.player
                if result.cookie_value:
                    set_remember_cookie(result.cookie_value)
                st.rerun()
            st.error(result.message)

    with tab_new:
        st.caption("One nickname. One emoji. One PIN. That's it.")
        with st.form("signup_form"):
            nickname = st.text_input("Choose a nickname", max_chars=15)
            avatar = st.text_input("Choose one emoji", max_chars=8, placeholder="🏈")
            pin = st.text_input("Create a 4-digit PIN", type="password", max_chars=4)
            pin2 = st.text_input("Confirm PIN", type="password", max_chars=4)
            remember = st.checkbox("Keep me signed in this season", value=True, key="signup_remember")
            submitted = st.form_submit_button("Create Player", type="primary", use_container_width=True)
        if submitted:
            result = register_player(
                store,
                nickname=nickname,
                emoji=avatar,
                pin=pin,
                pin_confirm=pin2,
                pin_pepper=secret("PIN_PEPPER"),
                session_pepper=secret("SESSION_PEPPER"),
                remember=remember,
            )
            if result.ok:
                st.session_state.player = result.player
                if result.cookie_value:
                    set_remember_cookie(result.cookie_value)
                st.rerun()
            st.error(result.message)


def commish_login_ui() -> None:
    st.markdown("### Commissioner")
    st.caption("Separate admin access. This does not use a player PIN.")
    with st.form("commish_login"):
        username = st.text_input("Commissioner username")
        pin = st.text_input("6-digit admin PIN", type="password", max_chars=6)
        submit = st.form_submit_button("Enter Commissioner", type="primary", use_container_width=True)
    if submit:
        user_ok = safe_secret_match(username.strip().casefold(), secret("COMMISH_USERNAME").strip().casefold())
        pin_ok = safe_secret_match(pin, secret("COMMISH_PIN"))
        if user_ok and pin_ok:
            st.session_state.commish = True
            st.rerun()
        st.error("Commissioner login is incorrect.")


if st.session_state.commish:
    st.markdown("### Commissioner • Gate 1")
    st.success("Admin authentication is working. Commissioner tools are intentionally added in Gate 5.")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Check database", use_container_width=True):
            st.toast("Database connected." if store.healthcheck() else "Database check failed.")
    with col2:
        if st.button("Exit Commissioner", use_container_width=True):
            st.session_state.commish = False
            st.rerun()
    st.stop()

if st.session_state.player:
    foundation_home(st.session_state.player)
    if st.button("Sign Out", use_container_width=True):
        revoke_cookie_session(store, cookie_value)
        st.session_state.player = None
        st.session_state.remember_restore_attempted = True
        try:
            cookies.delete(COOKIE_NAME, key="delete_tsp_cookie_signout")
        except Exception:
            pass
        st.rerun()
    st.stop()

player_login_ui()
st.markdown("---")
with st.expander("Commissioner"):
    commish_login_ui()
