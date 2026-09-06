from __future__ import annotations

import json

import streamlit as st

from auth import login_player, register_player, restore_from_cookie, revoke_cookie_session
from config import (
    APP_NAME,
    COOKIE_NAME,
    REMEMBER_COOKIE_MAX_AGE,
    REMEMBER_STORAGE_KEY,
)
from security import safe_secret_match
from store import SupabaseStore
from ui import foundation_home, hero, inject_css, page_config

page_config()
inject_css()
hero()


# Browser-local remembered-login bridge.
# This intentionally mirrors the working Yahtzee architecture: a high-entropy
# revocable token is stored in first-party localStorage and synchronized to a
# first-party cookie. The PIN is never stored in the browser.
_remember_storage_component = st.components.v2.component(
    "pickem_remember_storage",
    html="<span aria-hidden='true'></span>",
    css=":host { display: none !important; height: 0 !important; }",
    js=r"""
    export default function({ data, setStateValue }) {
      const key = data?.storage_key || "tsp_remember_device_v1";
      const action = data?.action || "read";
      const token = data?.token || "";
      const nonce = data?.nonce || "";
      const cookieName = data?.cookie_name || "tsp_session_v1";
      const cookieMaxAge = Number(data?.cookie_max_age || 0);
      let stored = "";
      try {
        if (action === "set" && token) {
          window.localStorage.setItem(key, token);
        } else if (action === "delete") {
          window.localStorage.removeItem(key);
          document.cookie = `${cookieName}=; Path=/; Max-Age=0; Expires=Thu, 01 Jan 1970 00:00:00 GMT; SameSite=Lax; Secure`;
        }
        stored = window.localStorage.getItem(key) || "";
        if (stored) {
          document.cookie = `${cookieName}=${stored}; Path=/; Max-Age=${cookieMaxAge}; SameSite=Lax; Secure`;
        }
      } catch (err) {
        stored = "";
      }
      setStateValue("payload", JSON.stringify({
        token: stored,
        ready: true,
        ack: nonce
      }));
    }
    """,
)


def secret(name: str) -> str:
    try:
        return str(st.secrets[name])
    except Exception:
        return ""


@st.cache_resource(show_spinner=False)
def get_store(url: str, service_key: str) -> SupabaseStore:
    return SupabaseStore(url, service_key)


def supabase_server_key() -> str:
    # Match the current Yahtzee secret name while retaining compatibility with
    # the original Gate 1 name.
    return secret("SUPABASE_SECRET_KEY") or secret("SUPABASE_SERVICE_ROLE_KEY")


required = ["SUPABASE_URL", "PIN_PEPPER", "SESSION_PEPPER", "COMMISH_USERNAME", "COMMISH_PIN"]
missing = [name for name in required if not secret(name)]
if not supabase_server_key():
    missing.append("SUPABASE_SECRET_KEY")
if missing:
    st.error("App setup is incomplete. Add the required secrets before using Gate 1.")
    with st.expander("Setup details"):
        st.code("Missing: " + ", ".join(missing))
        st.write("Use `.streamlit/secrets.toml.example` as the template. Never commit the real secrets file.")
    st.stop()

store = get_store(secret("SUPABASE_URL"), supabase_server_key())


# -----------------------------
# Gate 1 session state
# -----------------------------
if "player" not in st.session_state:
    st.session_state.player = None
if "commish" not in st.session_state:
    st.session_state.commish = False
if "active_device_token" not in st.session_state:
    st.session_state.active_device_token = None
if "remember_restore_checked" not in st.session_state:
    st.session_state.remember_restore_checked = False
if "remember_storage_command" not in st.session_state:
    st.session_state.remember_storage_command = None
if "remember_storage_nonce" not in st.session_state:
    st.session_state.remember_storage_nonce = 0


def _browser_remember_cookie() -> str:
    """Read the first-party token from the initial browser request."""
    try:
        return str(st.context.cookies.get(COOKIE_NAME, "") or "").strip()
    except Exception:
        return ""


def _next_remember_storage_nonce() -> str:
    st.session_state.remember_storage_nonce = int(st.session_state.get("remember_storage_nonce", 0)) + 1
    return str(st.session_state.remember_storage_nonce)


def _queue_remember_storage_set(token: str) -> None:
    st.session_state.remember_storage_command = {
        "action": "set",
        "token": str(token),
        "nonce": _next_remember_storage_nonce(),
    }


def _queue_remember_storage_delete() -> None:
    st.session_state.remember_storage_command = {
        "action": "delete",
        "token": "",
        "nonce": _next_remember_storage_nonce(),
    }


def _queue_remember_cookie_set(token: str) -> None:
    # The first-party Components-v2 bridge writes BOTH localStorage and the
    # first-party cookie. Keep one browser command path so auth actions never
    # compete with a second hidden widget/script rerun.
    _queue_remember_storage_set(token)


def _queue_remember_cookie_delete() -> None:
    _queue_remember_storage_delete()


def render_remember_storage_bridge() -> dict:
    """Read/write the season token through first-party browser localStorage."""
    command = st.session_state.get("remember_storage_command") or {}
    action = str(command.get("action") or "read")
    token = str(command.get("token") or "")
    nonce = str(command.get("nonce") or "")
    default_payload = json.dumps({"token": "", "ready": False, "ack": ""})
    try:
        result = _remember_storage_component(
            data={
                "storage_key": REMEMBER_STORAGE_KEY,
                "action": action,
                "token": token,
                "nonce": nonce,
                "cookie_name": COOKIE_NAME,
                "cookie_max_age": REMEMBER_COOKIE_MAX_AGE,
            },
            default={"payload": default_payload},
            on_payload_change=lambda: None,
            key="pickem_remember_storage_bridge",
        )
        payload_raw = getattr(result, "payload", default_payload) or default_payload
        payload = json.loads(str(payload_raw))
        if nonce and str(payload.get("ack") or "") == nonce:
            st.session_state.remember_storage_command = None
        return {
            "token": str(payload.get("token") or "").strip(),
            "ready": bool(payload.get("ready")),
        }
    except Exception:
        # The first-party cookie remains a compatibility fallback. A browser
        # that blocks localStorage can still use the app normally.
        return {"token": "", "ready": True}


def _process_pending_storage_command() -> bool:
    """Finish a queued browser write/delete before exposing clickable UI.

    Components-v2 reports its acknowledgement on a rerun. While that command
    is still pending, stop the page so the hidden component cannot steal the
    user's first click on Sign In / Sign Out / Commissioner actions.
    """
    if not st.session_state.get("remember_storage_command"):
        return True
    render_remember_storage_bridge()
    if st.session_state.get("remember_storage_command"):
        st.caption("Finishing secure sign-in…")
        st.stop()
    return True


def _apply_restore_result(result, token: str) -> bool:
    if result.ok:
        st.session_state.remember_restore_checked = True
        st.session_state.player = result.player
        st.session_state.active_device_token = token
        return True
    if result.message == "TEMPORARY_SESSION_CHECK_FAILURE":
        # Keep the browser token intact. A later rerun/refresh can retry.
        return False
    return False


def _restore_remembered_cookie_fast_path(cookie_token: str) -> bool:
    """Restore directly from the first-request cookie before mounting localStorage."""
    if st.session_state.player or st.session_state.remember_restore_checked:
        return False
    token = str(cookie_token or "").strip()
    if not token:
        return False
    result = restore_from_cookie(store, token, session_pepper=secret("SESSION_PEPPER"))
    if _apply_restore_result(result, token):
        return True
    # A stale/invalid cookie should not suppress a potentially newer valid
    # localStorage token. Only delete once localStorage has also had a chance.
    return False


def _restore_remembered_player(storage_state: dict | None = None, *, cookie_token: str | None = None) -> None:
    """Restore from localStorage first, with an optional cookie fallback."""
    if st.session_state.player or st.session_state.remember_restore_checked:
        return
    storage_state = storage_state or {}
    if cookie_token is None:
        cookie_token = _browser_remember_cookie()
    cookie_token = str(cookie_token or "").strip()
    storage_token = str(storage_state.get("token") or "").strip()
    storage_ready = bool(storage_state.get("ready"))

    # Components v2 returns browser localStorage on the next rerun. Do not mark
    # the restore attempt complete until that read is ready unless a cookie
    # already restored us on the fast path.
    if not cookie_token and not storage_ready:
        return

    token = storage_token or cookie_token
    if not token:
        st.session_state.remember_restore_checked = True
        return

    result = restore_from_cookie(store, token, session_pepper=secret("SESSION_PEPPER"))
    if _apply_restore_result(result, token):
        return
    if result.message == "TEMPORARY_SESSION_CHECK_FAILURE":
        return

    st.session_state.remember_restore_checked = True
    _queue_remember_cookie_delete()


def finish_player_auth(result, *, auth_slot=None) -> None:
    # Clear the submitted auth UI before the browser-storage acknowledgement
    # rerun. Streamlit otherwise keeps stale form elements visible as ghosts,
    # which can briefly look like a duplicated sign-in panel.
    if auth_slot is not None:
        try:
            auth_slot.empty()
        except Exception:
            pass
    st.session_state.player = result.player
    st.session_state.remember_restore_checked = True
    if result.cookie_value:
        st.session_state.active_device_token = result.cookie_value
        _queue_remember_cookie_set(result.cookie_value)
    else:
        st.session_state.active_device_token = None
    st.rerun()


def player_login_ui(*, auth_slot=None) -> None:
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
                finish_player_auth(result, auth_slot=auth_slot)
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
                finish_player_auth(result, auth_slot=auth_slot)
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


# -----------------------------
# Remembered-login restore
# -----------------------------
# A queued set/delete comes from a deliberate user action on the previous run.
# Finish it FIRST and do not render other clickable UI until the browser has
# acknowledged it. This removes the double-click behavior seen in Gate 1.
_process_pending_storage_command()

_storage_state = {"token": "", "ready": True}
if not st.session_state.player and not st.session_state.remember_restore_checked:
    _cookie_token = _browser_remember_cookie()
    _cookie_restored = _restore_remembered_cookie_fast_path(_cookie_token)
    if not _cookie_restored:
        _storage_state = render_remember_storage_bridge()
        # Cookie was already tried. Let localStorage choose the fallback so a
        # stale cookie cannot hide a newer valid browser token.
        _restore_remembered_player(_storage_state, cookie_token="")

        # If localStorage has not answered yet, avoid flashing a sign-in form
        # and—more importantly—avoid mounting clickable widgets that could
        # compete with the component's automatic rerun.
        if not st.session_state.player and not st.session_state.remember_restore_checked and not _storage_state.get("ready"):
            st.caption("Checking remembered sign-in…")
            st.stop()


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
        token = st.session_state.get("active_device_token") or _browser_remember_cookie()
        revoke_cookie_session(store, token)
        _queue_remember_cookie_delete()
        # Prevent the still-visible initial cookie snapshot from restoring on
        # the immediate sign-out rerun.
        st.session_state.remember_restore_checked = True
        st.session_state.player = None
        st.session_state.active_device_token = None
        st.rerun()
    st.stop()

_auth_slot = st.empty()
with _auth_slot.container():
    player_login_ui(auth_slot=_auth_slot)
st.markdown("---")
with st.expander("Commissioner"):
    commish_login_ui()
