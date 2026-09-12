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
.block-container { max-width: 640px; padding-top: 2.25rem; padding-bottom: 7.2rem; }
[data-testid="stHeader"] { background: rgba(247,249,250,.94) !important; }
h1,h2,h3 { letter-spacing:-.025em; color:var(--ink); }
h3 { font-size:1.42rem !important; line-height:1.15 !important; margin-top:1.2rem !important; margin-bottom:.55rem !important; }
h4 { font-size:1.05rem !important; line-height:1.2 !important; margin-top:.9rem !important; margin-bottom:.45rem !important; }
[data-testid="stCaptionContainer"] { margin-top:-.08rem; }
.hero { padding:.55rem 0 .45rem; overflow:visible; }
.hero-kicker { font-size:.78rem; line-height:1.35; padding-top:.12rem; font-weight:800; letter-spacing:.12em; color:var(--teal); text-transform:uppercase; overflow:visible; }
.hero-title { font-size:1.86rem; line-height:1.04; font-weight:850; letter-spacing:-.045em; color:var(--ink); margin:.2rem 0; }
.hero-sub { color:var(--muted); font-size:.94rem; }
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
.status-danger { background:#FFF1F0; border:1px solid #F3C3BF; border-radius:14px; padding:.8rem .9rem; color:#8F241D; }
.status-test { background:#EEF4FF; border:1px solid #C6D7FA; border-radius:14px; padding:.8rem .9rem; color:#294E8C; }
.position-pill { display:inline-block; min-width:2.4rem; padding:.18rem .45rem; border-radius:999px; text-align:center; background:#ECF8F6; color:#155E56; font-size:.75rem; font-weight:850; }
.player-name { font-weight:820; font-size:1rem; }
.meta { color:var(--muted); font-size:.84rem; margin-top:.12rem; }
.badge-q { display:inline-block; padding:.12rem .42rem; border-radius:999px; background:#FFF2D8; color:#8A5100; font-size:.72rem; font-weight:850; margin-left:.35rem; }
.badge-out { display:inline-block; padding:.12rem .42rem; border-radius:999px; background:#FDE8E7; color:#A22B24; font-size:.72rem; font-weight:850; margin-left:.35rem; }
/* Player-selection cards: the visible card is the native Streamlit button.
   This avoids fragile invisible overlays and makes the entire rectangle tappable. */
div[class*="st-key-pickbtn_"] [data-testid="stButton"] {
  width:100% !important;
  margin:.25rem 0 !important;
}
div[class*="st-key-pickbtn_"] [data-testid="stButton"] button,
div[class*="st-key-pickbtn_"] [data-testid^="stBaseButton"] {
  width:100% !important;
  min-height:68px !important;
  height:auto !important;
  padding:.5rem .8rem !important;
  border-radius:16px !important;
  border:1px solid #D6DEE3 !important;
  background:#FFFFFF !important;
  color:var(--ink) !important;
  box-shadow:none !important;
  cursor:pointer !important;
}
div[class*="st-key-pickbtn_"] [data-testid="stButton"] button:hover,
div[class*="st-key-pickbtn_"] [data-testid^="stBaseButton"]:hover {
  background:#F3F7F7 !important;
  border-color:#BFC9CF !important;
}
div[class*="st-key-pickbtn_selected_"] [data-testid="stButton"] button,
div[class*="st-key-pickbtn_selected_"] [data-testid^="stBaseButton"] {
  background:#E7F7F4 !important;
  border:2px solid var(--teal) !important;
  box-shadow:0 0 0 2px rgba(15,118,110,.08) !important;
}
div[class*="st-key-pickbtn_"] [data-testid="stButton"] button p,
div[class*="st-key-pickbtn_"] [data-testid^="stBaseButton"] p {
  width:100% !important;
  margin:0 !important;
  white-space:pre-line !important;
  text-align:center !important;
  line-height:1.3 !important;
  font-size:.95rem !important;
  color:var(--ink) !important;
}
div[class*="st-key-pickbtn_"] [data-testid="stButton"] button p strong,
div[class*="st-key-pickbtn_"] [data-testid^="stBaseButton"] p strong {
  font-size:1rem !important;
  font-weight:820 !important;
}
div[class*="st-key-pickbtn_"] [data-testid="stButton"] button:disabled,
div[class*="st-key-pickbtn_"] [data-testid^="stBaseButton"]:disabled {
  opacity:.62 !important;
  cursor:not-allowed !important;
}
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
/* Player signup PINs are intentionally phone/tel inputs so iOS opens a numeric
   keypad and does not treat them as account passwords. Mask the four digits
   visually without changing the underlying input back to type=password. */
div[class*="st-key-signup_pin"] input {
  -webkit-text-security:disc;
}
[data-testid="stCheckbox"] label, [data-testid="stWidgetLabel"] { color:var(--ink) !important; }

/* Keep the product visually light even when the phone/browser is in dark mode.
   Streamlit renders popovers/menus in portals outside the normal .stApp tree,
   so these surfaces need their own explicit light-theme contract. */
[data-testid="stExpander"],
[data-testid="stExpander"] details,
[data-testid="stExpander"] summary,
[data-testid="stExpanderDetails"],
[data-testid="stPopoverBody"],
[data-baseweb="popover"],
[data-baseweb="popover"] > div,
[data-baseweb="menu"],
[role="dialog"] {
  background:#FFFFFF !important;
  color:var(--ink) !important;
  color-scheme:light !important;
}
[data-testid="stExpander"] *,
[data-testid="stPopoverBody"] *,
[data-baseweb="popover"] *,
[data-baseweb="menu"] *,
[role="dialog"] * {
  color:var(--ink) !important;
  -webkit-text-fill-color:var(--ink) !important;
}
[data-baseweb="select"] > div,
[data-baseweb="input"] > div {
  background:#FFFFFF !important;
  color:var(--ink) !important;
  color-scheme:light !important;
}

/* The public app does not need Streamlit's in-app developer toolbar.
   Community Cloud's owner-only Manage App control is host chrome and may still
   appear, so the mobile nav also reserves a safe noninteractive zone for it. */
[data-testid="stToolbar"], .stDeployButton { visibility:hidden !important; }
hr { border-color:var(--line); }

/* Gate 4 live Sunday / social UI */
.sunday-status { background:#FFFFFF; border:1px solid var(--line); border-radius:18px; padding:.9rem .95rem; margin:.65rem 0 .8rem; box-shadow:0 3px 16px rgba(23,32,39,.04); }
.sunday-status-ok { border-color:#B9E3DD; background:#F7FCFB; }
.sunday-status-warn { border-color:#F1D69B; background:#FFFCF4; }
.sunday-status-danger { border-color:#F3C3BF; background:#FFF8F7; }
.sunday-status-head { display:flex; align-items:center; gap:.66rem; }
.sunday-status-icon { font-size:1.45rem; line-height:1; }
.sunday-status-title { font-size:1.16rem; line-height:1.15; font-weight:900; letter-spacing:-.025em; color:var(--ink); margin-top:.08rem; }
.sunday-status-sub { font-size:.9rem; font-weight:720; color:#46545D; margin:.55rem 0 .48rem; }
.sunday-status-lines { display:grid; grid-template-columns:1fr 1fr; gap:.45rem; padding-top:.5rem; border-top:1px solid rgba(214,222,227,.75); color:var(--muted); font-size:.84rem; font-weight:700; }
.story-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:.55rem; margin:.25rem 0 .75rem; }
.story-card { background:#FFFFFF; border:1px solid var(--line); border-radius:15px; padding:.76rem; min-height:112px; box-shadow:0 2px 10px rgba(23,32,39,.03); }
.story-icon { font-size:1.18rem; }
.story-title { color:var(--teal); text-transform:uppercase; letter-spacing:.06em; font-size:.7rem; font-weight:850; margin:.2rem 0; }
.story-main { font-size:1rem; font-weight:820; color:var(--ink); }
.story-more { color:var(--teal); font-size:.78rem; font-weight:760; margin-top:.32rem; }
.recap-hero { background:linear-gradient(135deg,#F4FBFA 0%,#FFFFFF 62%); border:1px solid #B9E3DD; border-radius:20px; padding:1rem 1.05rem; margin:.6rem 0 .8rem; box-shadow:0 4px 18px rgba(23,32,39,.05); text-align:center; }
.recap-kicker { color:var(--teal); font-size:.72rem; font-weight:900; letter-spacing:.1em; }
.recap-champion { color:var(--ink); font-size:1.5rem; line-height:1.12; font-weight:920; letter-spacing:-.04em; margin:.24rem 0 .12rem; }
.recap-score { color:#155E56; font-size:1.02rem; font-weight:820; }
.recap-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:.55rem; margin:.25rem 0 .7rem; }
.recap-card { background:#FFFFFF; border:1px solid var(--line); border-radius:15px; padding:.78rem; min-height:112px; box-shadow:0 2px 10px rgba(23,32,39,.03); }
.you-strip { display:flex; justify-content:space-between; align-items:center; background:#ECF8F6; border:1px solid #B9E3DD; color:#155E56; padding:.58rem .72rem; border-radius:13px; margin:.4rem 0 .5rem; }
.score-row { display:flex; align-items:center; gap:.6rem; background:#FFFFFF; border-bottom:1px solid #EEF1F3; padding:.58rem .12rem; }
.score-row:last-child { border-bottom:0; }
.score-body { flex:1; min-width:0; }
.score-points { font-weight:850; font-size:1.05rem; min-width:3.3rem; text-align:right; }
.season-row { display:flex; justify-content:space-between; align-items:center; gap:.7rem; background:#FFFFFF; border:1px solid var(--line); border-radius:13px; padding:.62rem .72rem; margin:.32rem 0; }
.season-points { font-size:1.05rem; font-weight:850; white-space:nowrap; }
.history-row { display:flex; justify-content:space-between; align-items:center; gap:.7rem; padding:.5rem 0; border-bottom:1px solid #EEF1F3; }
.history-row:last-child { border-bottom:0; }
/* Full-row leaderboard buttons. */
div[class*="st-key-leaderbtn_"] { margin:.28rem 0 !important; }
div[class*="st-key-leaderbtn_"] [data-testid="stButton"] button,
div[class*="st-key-leaderbtn_"] [data-testid^="stBaseButton"] { width:100% !important; min-height:52px !important; justify-content:flex-start !important; text-align:left !important; background:#FFFFFF !important; color:var(--ink) !important; border:1px solid var(--line) !important; border-radius:14px !important; padding:.6rem .76rem !important; box-shadow:0 1px 8px rgba(23,32,39,.025) !important; }
div[class*="st-key-leaderbtn_"] [data-testid="stButton"] button p,
div[class*="st-key-leaderbtn_"] [data-testid^="stBaseButton"] p { width:100% !important; text-align:left !important; margin:0 !important; font-weight:760 !important; color:var(--ink) !important; }
div[class*="st-key-leaderbtn_"] [data-testid="stButton"] button:hover,
div[class*="st-key-leaderbtn_"] [data-testid^="stBaseButton"]:hover { background:#F3F7F7 !important; border-color:#9CCFC8 !important; transform:translateY(-1px); }

.season-left { min-width:0; }
.season-name { font-weight:820; color:var(--ink); }
.you-badge { display:inline-block; margin-left:.3rem; padding:.08rem .35rem; border-radius:999px; background:#ECF8F6; color:#155E56; font-size:.66rem; letter-spacing:.04em; font-weight:900; vertical-align:.08rem; }
.history-card { background:#FFFFFF; border:1px solid var(--line); border-radius:15px; padding:.78rem .86rem; box-shadow:0 2px 10px rgba(23,32,39,.03); margin:.3rem 0 .65rem; }
.history-head { display:flex; justify-content:space-between; align-items:center; gap:.8rem; padding-bottom:.45rem; border-bottom:1px solid #EEF1F3; margin-bottom:.15rem; }
.profile-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:.5rem; margin:.35rem 0 .8rem; }
.profile-stat { background:#FFFFFF; border:1px solid var(--line); border-radius:14px; padding:.68rem .66rem; min-height:92px; box-shadow:0 2px 10px rgba(23,32,39,.025); }
.profile-stat-icon { font-size:1.15rem; }
.profile-stat-value { font-size:1.45rem; line-height:1.1; font-weight:900; letter-spacing:-.04em; color:var(--ink); margin:.22rem 0 .15rem; }
.profile-stat-label { color:var(--muted); font-size:.76rem; font-weight:720; }

/* Gate 4 app navigation: mobile tab-bar pattern.
   Four persistent top-level destinations, consistent Material icons, labels below
   icons, generous touch targets, and a compact floating surface above safe area. */
div[class*="st-key-gate4_nav"] {
  position:fixed !important;
  left:50% !important;
  transform:translateX(-50%) !important;
  bottom:calc(.55rem + env(safe-area-inset-bottom, 0px)) !important;
  z-index:999 !important;
  width:min(520px, calc(100vw - 1rem)) !important;
  background:rgba(255,255,255,.90) !important;
  -webkit-backdrop-filter:blur(18px) saturate(1.15);
  backdrop-filter:blur(18px) saturate(1.15);
  border:1px solid rgba(214,222,227,.92);
  border-radius:23px;
  padding:.3rem .4rem !important;
  box-shadow:0 12px 34px rgba(23,32,39,.13);
}
div[class*="st-key-gate4_nav"] [role="radiogroup"],
div[class*="st-key-gate4_nav"] [data-testid="stSegmentedControl"] {
  width:100% !important;
  background:transparent !important;
  gap:.08rem !important;
  overflow:visible !important;
}
div[class*="st-key-gate4_nav"] button {
  flex:1 1 0 !important;
  min-width:0 !important;
  min-height:58px !important;
  padding:.28rem .12rem .34rem !important;
  border:0 !important;
  border-radius:17px !important;
  background:transparent !important;
  color:#78848D !important;
  box-shadow:none !important;
}
div[class*="st-key-gate4_nav"] button p {
  display:flex !important;
  flex-direction:column !important;
  align-items:center !important;
  justify-content:center !important;
  gap:.12rem !important;
  width:100% !important;
  margin:0 !important;
  overflow:visible !important;
  text-overflow:clip !important;
  white-space:nowrap !important;
  line-height:1.02 !important;
  font-size:.66rem !important;
  font-weight:720 !important;
  letter-spacing:.005em !important;
}
div[class*="st-key-gate4_nav"] button p span {
  display:inline-flex !important;
  align-items:center !important;
  justify-content:center !important;
  min-width:42px !important;
  height:25px !important;
  padding:0 .62rem !important;
  border-radius:999px !important;
  font-size:1.22rem !important;
  line-height:1 !important;
  transition:background .14s ease,color .14s ease,transform .14s ease;
}
div[class*="st-key-gate4_nav"] button[aria-pressed="true"] {
  background:transparent !important;
  color:#155E56 !important;
}
div[class*="st-key-gate4_nav"] button[aria-pressed="true"] p { font-weight:850 !important; }
div[class*="st-key-gate4_nav"] button[aria-pressed="true"] p span {
  background:#DDF3EF !important;
  color:#0F766E !important;
}
div[class*="st-key-gate4_nav"] button:hover { background:#F5F8F8 !important; color:#155E56 !important; }
div[class*="st-key-gate4_nav"] button:focus-visible { outline:2px solid #58AAA0 !important; outline-offset:1px !important; }
/* Champion moment: short football flood, non-blocking and reduced-motion safe. */
.champion-overlay { position:fixed; inset:0; z-index:2000; overflow:hidden; background:rgba(247,249,250,.96); pointer-events:none; animation:champion-hide 3.1s ease forwards; display:flex; align-items:center; justify-content:center; }
.champion-card { position:relative; z-index:3; text-align:center; padding:1.35rem 1.1rem; background:#FFFFFF; border:1px solid #B9E3DD; border-radius:22px; box-shadow:0 12px 40px rgba(23,32,39,.16); width:min(440px,calc(100vw - 2rem)); }
.champion-name { font-size:1.55rem; font-weight:900; letter-spacing:-.035em; margin:.3rem 0; }
.champion-score { font-size:1.15rem; font-weight:800; color:#155E56; margin-bottom:.25rem; }
.football { position:absolute; top:-2rem; z-index:2; font-size:1.25rem; animation:football-fall 2.6s ease-in forwards; }
.football.f0 { left:0%; animation-delay:0.00s; animation-duration:2.00s; }
.football.f1 { left:37%; animation-delay:0.08s; animation-duration:2.16s; }
.football.f2 { left:74%; animation-delay:0.16s; animation-duration:2.32s; }
.football.f3 { left:15%; animation-delay:0.24s; animation-duration:2.48s; }
.football.f4 { left:52%; animation-delay:0.32s; animation-duration:2.64s; }
.football.f5 { left:89%; animation-delay:0.40s; animation-duration:2.00s; }
.football.f6 { left:30%; animation-delay:0.48s; animation-duration:2.16s; }
.football.f7 { left:67%; animation-delay:0.56s; animation-duration:2.32s; }
.football.f8 { left:8%; animation-delay:0.00s; animation-duration:2.48s; }
.football.f9 { left:45%; animation-delay:0.08s; animation-duration:2.64s; }
.football.f10 { left:82%; animation-delay:0.16s; animation-duration:2.00s; }
.football.f11 { left:23%; animation-delay:0.24s; animation-duration:2.16s; }
.football.f12 { left:60%; animation-delay:0.32s; animation-duration:2.32s; }
.football.f13 { left:1%; animation-delay:0.40s; animation-duration:2.48s; }
.football.f14 { left:38%; animation-delay:0.48s; animation-duration:2.64s; }
.football.f15 { left:75%; animation-delay:0.56s; animation-duration:2.00s; }
.football.f16 { left:16%; animation-delay:0.00s; animation-duration:2.16s; }
.football.f17 { left:53%; animation-delay:0.08s; animation-duration:2.32s; }
.football.f18 { left:90%; animation-delay:0.16s; animation-duration:2.48s; }
.football.f19 { left:31%; animation-delay:0.24s; animation-duration:2.64s; }
.football.f20 { left:68%; animation-delay:0.32s; animation-duration:2.00s; }
.football.f21 { left:9%; animation-delay:0.40s; animation-duration:2.16s; }
.football.f22 { left:46%; animation-delay:0.48s; animation-duration:2.32s; }
.football.f23 { left:83%; animation-delay:0.56s; animation-duration:2.48s; }

@keyframes football-fall { 0% { transform:translateY(-10vh) rotate(0deg); opacity:0; } 12% { opacity:1; } 100% { transform:translateY(115vh) rotate(620deg); opacity:.18; } }
@keyframes champion-hide { 0%,82% { opacity:1; visibility:visible; } 100% { opacity:0; visibility:hidden; } }
@media (prefers-reduced-motion: reduce) { .football { animation:none !important; opacity:.12; top:1rem; } }

@media (max-width: 560px) {
  .story-grid { grid-template-columns:1fr; }
  .recap-grid { grid-template-columns:1fr; }
  .sunday-status-lines { grid-template-columns:1fr; gap:.32rem; }
  .profile-grid { grid-template-columns:repeat(2,minmax(0,1fr)); }
}
@media (max-width: 480px) {
  .block-container { padding-top:2.15rem; padding-left:.9rem; padding-right:.9rem; padding-bottom:7rem; }
  .hero { padding-top:.65rem; }
  .hero-kicker { line-height:1.5; padding-top:.18rem; }
  .hero-title { font-size:1.64rem; }
  div[class*="st-key-gate4_nav"] {
    width:calc(100vw - .7rem) !important;
    bottom:calc(.35rem + env(safe-area-inset-bottom, 0px)) !important;
    border-radius:21px;
    box-sizing:border-box !important;
    /* Community Cloud shows an owner-only Manage App/avatar control in the
       lower-right. Reserve that area so Profile stays tappable for the owner,
       while normal viewers simply see a subtle branded end-cap. */
    padding:.3rem 7rem .3rem .4rem !important;
  }
  div[class*="st-key-gate4_nav"]::after {
    content:"🏈";
    position:absolute;
    right:2rem;
    top:50%;
    transform:translateY(-50%);
    opacity:.18;
    font-size:1.15rem;
    pointer-events:none;
  }
  div[class*="st-key-gate4_nav"] button { min-height:56px !important; }
  div[class*="st-key-gate4_nav"] button p { font-size:.63rem !important; }
  div[class*="st-key-gate4_nav"] button p span { min-width:38px !important; height:24px !important; font-size:1.16rem !important; }
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
