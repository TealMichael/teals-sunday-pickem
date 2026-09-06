from __future__ import annotations

import streamlit as st

from config import APP_NAME, APP_TAGLINE, APP_VERSION


def page_config() -> None:
    st.set_page_config(page_title=APP_NAME, page_icon="🏈", layout="centered", initial_sidebar_state="collapsed")


def inject_css() -> None:
    st.markdown(
        """
<style>
:root { color-scheme: light; --teal:#0F766E; --ink:#172027; --muted:#64727D; --line:#E5EAED; --page:#F7F9FA; --surface:#FFFFFF; --warn:#A05A00; --danger:#B42318; }
html, body, [data-testid="stAppViewContainer"], .stApp { background:var(--page) !important; color:var(--ink) !important; }
.block-container { max-width: 680px; padding-top: 2.25rem; padding-bottom: 5rem; }
[data-testid="stHeader"] { background: rgba(247,249,250,.94) !important; }
h1,h2,h3 { letter-spacing:-.025em; color:var(--ink); }
.hero { padding: .8rem 0 .65rem 0; overflow: visible; }
.hero-kicker { font-size:.78rem; line-height:1.35; padding-top:.12rem; font-weight:800; letter-spacing:.12em; color:var(--teal); text-transform:uppercase; overflow:visible; }
.hero-title { font-size:2rem; line-height:1.05; font-weight:850; letter-spacing:-.045em; color:var(--ink); margin:.25rem 0; }
.hero-sub { color:var(--muted); font-size:1rem; }
.card { background:var(--surface); border:1px solid var(--line); border-radius:18px; padding:1rem; box-shadow:0 3px 16px rgba(23,32,39,.04); margin:.65rem 0; }
.card-tight { background:var(--surface); border:1px solid var(--line); border-radius:16px; padding:.8rem .9rem; margin:.48rem 0; }
.identity { display:flex; align-items:center; gap:.7rem; }
.avatar { width:46px; height:46px; display:flex; align-items:center; justify-content:center; border-radius:14px; background:#ECF8F6; font-size:1.55rem; }
.small { color:var(--muted); font-size:.9rem; }
.eyebrow { color:var(--teal); text-transform:uppercase; letter-spacing:.09em; font-size:.74rem; font-weight:850; }
.week-title { font-size:1.35rem; font-weight:850; letter-spacing:-.03em; margin:.1rem 0; }
.big-number { font-size:1.9rem; font-weight:850; letter-spacing:-.04em; }
.status-ok { background:#ECF8F6; border:1px solid #B9E3DD; border-radius:14px; padding:.8rem .9rem; color:#155E56; }
.status-warn { background:#FFF8E7; border:1px solid #F1D69B; border-radius:14px; padding:.8rem .9rem; color:#7A4A00; }
.status-test { background:#EEF4FF; border:1px solid #C6D7FA; border-radius:14px; padding:.8rem .9rem; color:#294E8C; }
.position-pill { display:inline-block; min-width:2.4rem; padding:.18rem .45rem; border-radius:999px; text-align:center; background:#ECF8F6; color:#155E56; font-size:.75rem; font-weight:850; }
.player-name { font-weight:820; font-size:1rem; }
.meta { color:var(--muted); font-size:.84rem; margin-top:.12rem; }
.badge-q { display:inline-block; padding:.12rem .42rem; border-radius:999px; background:#FFF2D8; color:#8A5100; font-size:.72rem; font-weight:850; margin-left:.35rem; }
.badge-out { display:inline-block; padding:.12rem .42rem; border-radius:999px; background:#FDE8E7; color:#A22B24; font-size:.72rem; font-weight:850; margin-left:.35rem; }
/* Player-selection cards: custom visible content + one invisible full-card tap target. */
.pick-card-content { position:relative; z-index:1; text-align:center; padding:.62rem .7rem .66rem; pointer-events:none; }
.pick-card-name-row { display:flex; flex-wrap:wrap; align-items:center; justify-content:center; gap:.34rem; line-height:1.25; }
.pick-card-name { font-size:1rem; font-weight:820; color:var(--ink); }
.pick-card-meta { margin-top:.28rem; color:var(--ink); font-size:.92rem; }
.pick-check { font-weight:900; color:#155E56; font-size:1.05rem; }
div[class*="st-key-pickcard_"] { position:relative !important; background:#FFFFFF !important; border-radius:16px !important; border-color:#D6DEE3 !important; padding:0 !important; margin:.48rem 0 !important; overflow:hidden !important; }
div[class*="st-key-pickcard_selected_"] { border-color:#8FD3CA !important; background:#F7FCFB !important; }
/* Keep Streamlit's button wrappers out of the positioning chain so the
   actual invisible button can use the entire keyed card as its containing box. */
div[class*="st-key-pickcard_"] [data-testid="stButton"],
div[class*="st-key-pickcard_"] [data-testid="stButton"] > div {
  position:static !important;
  width:auto !important;
  height:0 !important;
  min-height:0 !important;
  margin:0 !important;
  padding:0 !important;
}
div[class*="st-key-pickcard_"] [data-testid="stBaseButton-tertiary"] {
  position:absolute !important;
  inset:0 !important;
  z-index:20 !important;
  width:100% !important;
  height:100% !important;
  min-height:100% !important;
  margin:0 !important;
  padding:0 !important;
  border:0 !important;
  opacity:0 !important;
  cursor:pointer !important;
}
div[class*="st-key-pickcard_"] [data-testid="stBaseButton-tertiary"]:disabled { cursor:not-allowed !important; }
div[class*="st-key-pickcard_"]:has([data-testid="stBaseButton-tertiary"]:hover) { background:#F3F7F7 !important; border-color:#BFC9CF !important; }
.lineup-row { display:flex; align-items:center; gap:.65rem; padding:.58rem 0; border-bottom:1px solid #EEF1F3; }
.lineup-row:last-child { border-bottom:0; }
.onboard-grid { display:grid; grid-template-columns:1fr; gap:.6rem; margin:.7rem 0 1rem; }
.onboard-card { background:#FFFFFF; border:1px solid var(--line); border-radius:16px; padding:.9rem; }
.onboard-num { width:28px; height:28px; border-radius:999px; background:#ECF8F6; color:#155E56; display:inline-flex; align-items:center; justify-content:center; font-weight:900; margin-right:.45rem; }
[data-testid="stForm"] { border:1px solid var(--line); border-radius:18px; padding:1rem; background:var(--surface) !important; }
.stButton button, [data-testid="stFormSubmitButton"] button { min-height:46px; border-radius:12px; font-weight:750; }
button[kind="primary"], [data-testid="stBaseButton-primary"], [data-testid="stBaseButton-primaryForm"] { background:var(--teal) !important; color:#FFFFFF !important; border-color:var(--teal) !important; }
.stButton button[kind="secondary"], [data-testid="stBaseButton-secondary"] { background:#FFFFFF !important; color:var(--ink) !important; -webkit-text-fill-color:var(--ink) !important; border:1px solid #D6DEE3 !important; }
.stButton button[kind="secondary"] *, [data-testid="stBaseButton-secondary"] * { color:var(--ink) !important; -webkit-text-fill-color:var(--ink) !important; }
.stButton button[kind="secondary"]:hover, [data-testid="stBaseButton-secondary"]:hover { background:#F3F5F7 !important; color:var(--ink) !important; border-color:#BFC9CF !important; }
[data-testid="stTextInput"] input { min-height:44px; border-radius:12px; background:#F3F5F7 !important; color:var(--ink) !important; -webkit-text-fill-color:var(--ink) !important; }
[data-testid="stTextInput"] input::placeholder { color:#8A969F !important; }
[data-testid="stCheckbox"] label, [data-testid="stWidgetLabel"] { color:var(--ink) !important; }
[data-testid="stExpander"] { background:var(--surface) !important; }
hr { border-color:var(--line); }
@media (max-width: 480px) {
  .block-container { padding-top:2.6rem; padding-left:1rem; padding-right:1rem; }
  .hero { padding-top:.65rem; }
  .hero-kicker { line-height:1.5; padding-top:.18rem; }
  .hero-title { font-size:1.78rem; }
}
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
<div class="card"><div class="identity"><div class="avatar">{emoji}</div><div><strong style="font-size:1.1rem">{nickname}</strong><br><span class="small">Your player account is ready.</span></div></div></div>
<div class="status-ok"><strong>Gate 1 foundation is live.</strong><br>Your identity, PIN, and remembered-device session are connected.</div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(f"Build {APP_VERSION}")
