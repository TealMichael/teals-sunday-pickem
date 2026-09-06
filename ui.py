from __future__ import annotations

import streamlit as st

from config import APP_NAME, APP_TAGLINE, APP_VERSION


def page_config() -> None:
    st.set_page_config(
        page_title=APP_NAME,
        page_icon="🏈",
        layout="centered",
        initial_sidebar_state="collapsed",
    )


def inject_css() -> None:
    st.markdown(
        """
<style>
:root { color-scheme: light; --teal:#0F766E; --ink:#172027; --muted:#64727D; --line:#E5EAED; --page:#F7F9FA; --surface:#FFFFFF; }
html, body, [data-testid="stAppViewContainer"], .stApp { background:var(--page) !important; color:var(--ink) !important; }
.block-container { max-width: 680px; padding-top: 2.25rem; padding-bottom: 4rem; }
[data-testid="stHeader"] { background: rgba(247,249,250,.94) !important; }
h1,h2,h3 { letter-spacing:-.025em; color:var(--ink); }
.hero { padding: .8rem 0 .65rem 0; overflow: visible; }
.hero-kicker { font-size:.78rem; line-height:1.35; padding-top:.12rem; font-weight:800; letter-spacing:.12em; color:var(--teal); text-transform:uppercase; overflow:visible; }
.hero-title { font-size:2rem; line-height:1.05; font-weight:850; letter-spacing:-.045em; color:var(--ink); margin:.25rem 0; }
.hero-sub { color:var(--muted); font-size:1rem; }
.card { background:var(--surface); border:1px solid var(--line); border-radius:18px; padding:1rem 1rem; box-shadow:0 3px 16px rgba(23,32,39,.04); margin:.65rem 0; }
.identity { display:flex; align-items:center; gap:.7rem; }
.avatar { width:46px; height:46px; display:flex; align-items:center; justify-content:center; border-radius:14px; background:#ECF8F6; font-size:1.55rem; }
.small { color:var(--muted); font-size:.9rem; }
.status-ok { background:#ECF8F6; border:1px solid #B9E3DD; border-radius:14px; padding:.8rem .9rem; color:#155E56; }
[data-testid="stForm"] { border:1px solid var(--line); border-radius:18px; padding:1rem; background:var(--surface) !important; }
.stButton button, [data-testid="stFormSubmitButton"] button { min-height:46px; border-radius:12px; font-weight:750; }
button[kind="primary"], [data-testid="stBaseButton-primary"], [data-testid="stBaseButton-primaryForm"] { background:var(--teal) !important; color:#FFFFFF !important; border-color:var(--teal) !important; }
.stButton button[kind="secondary"], [data-testid="stBaseButton-secondary"] { background:#FFFFFF !important; color:var(--ink) !important; -webkit-text-fill-color:var(--ink) !important; border:1px solid #D6DEE3 !important; }
.stButton button[kind="secondary"]:hover, [data-testid="stBaseButton-secondary"]:hover { background:#F3F5F7 !important; color:var(--ink) !important; border-color:#BFC9CF !important; }
[data-testid="stTextInput"] input { min-height:44px; border-radius:12px; background:#F3F5F7 !important; color:var(--ink) !important; -webkit-text-fill-color:var(--ink) !important; }
[data-testid="stTextInput"] input::placeholder { color:#8A969F !important; }
[data-testid="stCheckbox"] label, [data-testid="stWidgetLabel"] { color:var(--ink) !important; }
[data-testid="stExpander"] { background:var(--surface) !important; }
hr { border-color:var(--line); }
</style>
        """,
        unsafe_allow_html=True,
    )


def hero() -> None:
    st.markdown(
        f"""
<div class="hero">
  <div class="hero-kicker">Sunday football with friends</div>
  <div class="hero-title">🏈 {APP_NAME}</div>
  <div class="hero-sub">{APP_TAGLINE}</div>
</div>
        """,
        unsafe_allow_html=True,
    )


def foundation_home(player: dict) -> None:
    emoji = player.get("emoji", "🏈")
    nickname = player.get("nickname", "Player")
    st.markdown(
        f"""
<div class="card">
  <div class="identity">
    <div class="avatar">{emoji}</div>
    <div><strong style="font-size:1.1rem">{nickname}</strong><br><span class="small">Your player account is ready.</span></div>
  </div>
</div>
<div class="status-ok"><strong>Gate 1 foundation is live.</strong><br>Your identity, PIN, and remembered-device session are connected. The Week 1 game arrives in Gate 2.</div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(f"Build {APP_VERSION} • Foundation checkpoint")

