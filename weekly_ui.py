from __future__ import annotations

import html
import random
from datetime import datetime, timezone

import streamlit as st

from config import APP_VERSION
from weekly import (
    POSITIONS,
    et_label,
    first_incomplete_position,
    lineup_progress,
    next_position,
    picks_by_position,
    pool_is_ready,
    position_pool,
    previous_position,
    required_backup_positions,
    safe_status,
    week_phase,
)

UTC = timezone.utc


def _countdown(target_iso: str, label: str) -> None:
    safe_target = html.escape(str(target_iso), quote=True)
    safe_label = html.escape(label)
    st.components.v1.html(
        f"""
<div class="tsp-countdown-card">
  <div class="tsp-countdown-label">{safe_label}</div>
  <div class="tsp-countdown-grid" aria-label="Countdown">
    <div class="tsp-countdown-unit"><div id="tsp-days" class="tsp-countdown-value">--</div><div class="tsp-countdown-unit-label">DAYS</div></div>
    <div class="tsp-countdown-unit"><div id="tsp-hours" class="tsp-countdown-value">--</div><div class="tsp-countdown-unit-label">HRS</div></div>
    <div class="tsp-countdown-unit"><div id="tsp-minutes" class="tsp-countdown-value">--</div><div class="tsp-countdown-unit-label">MIN</div></div>
    <div class="tsp-countdown-unit"><div id="tsp-seconds" class="tsp-countdown-value">--</div><div class="tsp-countdown-unit-label">SEC</div></div>
  </div>
</div>
<style>
  :root {{ color-scheme: light; }}
  html, body {{ margin:0; padding:0; background:transparent; }}
  .tsp-countdown-card {{
    box-sizing:border-box;
    width:100%;
    font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
    background:#fff;
    border:1px solid #E5EAED;
    border-radius:18px;
    padding:13px 14px 14px;
    color:#172027;
  }}
  .tsp-countdown-label {{
    font-size:12px;
    line-height:1.25;
    font-weight:850;
    text-transform:uppercase;
    letter-spacing:.09em;
    color:#0F766E;
    margin-bottom:9px;
  }}
  .tsp-countdown-grid {{
    display:grid;
    grid-template-columns:repeat(4,minmax(0,1fr));
    gap:8px;
  }}
  .tsp-countdown-unit {{
    min-width:0;
    text-align:center;
    background:#F7F9FA;
    border:1px solid #EDF1F3;
    border-radius:12px;
    padding:8px 3px 7px;
  }}
  .tsp-countdown-value {{
    font-size:26px;
    line-height:1;
    font-weight:900;
    letter-spacing:-.04em;
    font-variant-numeric:tabular-nums;
  }}
  .tsp-countdown-unit-label {{
    margin-top:5px;
    font-size:9px;
    line-height:1;
    font-weight:850;
    letter-spacing:.09em;
    color:#677680;
  }}
  @media (max-width:420px) {{
    .tsp-countdown-card {{ padding:12px 10px 13px; }}
    .tsp-countdown-grid {{ gap:6px; }}
    .tsp-countdown-value {{ font-size:23px; }}
    .tsp-countdown-unit-label {{ font-size:8px; }}
  }}
</style>
<script>
const target = new Date("{safe_target}").getTime();
const dayEl = document.getElementById("tsp-days");
const hourEl = document.getElementById("tsp-hours");
const minuteEl = document.getElementById("tsp-minutes");
const secondEl = document.getElementById("tsp-seconds");
function pad(value) {{ return String(value).padStart(2, "0"); }}
function tick() {{
  const diff = Math.max(0, target - Date.now());
  const total = Math.floor(diff / 1000);
  const d = Math.floor(total / 86400);
  const h = Math.floor((total % 86400) / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  dayEl.textContent = pad(d);
  hourEl.textContent = pad(h);
  minuteEl.textContent = pad(m);
  secondEl.textContent = pad(s);
}}
tick(); setInterval(tick, 1000);
</script>
        """,
        height=116,
    )


def _player_lookup(pool: list[dict]) -> dict[str, dict]:
    return {str(row["id"]): row for row in pool}


def _display_name(row: dict | None) -> str:
    return str((row or {}).get("player_name") or "—")


def _player_meta(row: dict) -> str:
    team = str(row.get("team_abbr") or "—")
    opp = str(row.get("opponent_abbr") or "—")
    kickoff = et_label(row.get("kickoff_at"), include_date=False)
    return f"{team} vs {opp} • {kickoff}" if kickoff else f"{team} vs {opp}"


def _status_badge(row: dict) -> str:
    status = safe_status(row.get("availability_status"))
    if status == "QUESTIONABLE":
        return '<span class="badge-q">⚠ QUESTIONABLE</span>'
    if status == "OUT":
        return '<span class="badge-out">OUT</span>'
    return ""


def _stable_order(player_id: str, week_id: str, position: str, rows: list[dict]) -> list[dict]:
    key = f"pool_order::{player_id}::{week_id}::{position}"
    ids = [str(r["id"]) for r in rows]
    existing = list(st.session_state.get(key) or [])
    if set(existing) != set(ids) or len(existing) != len(ids):
        existing = ids[:]
        random.SystemRandom().shuffle(existing)
        st.session_state[key] = existing
    by_id = {str(r["id"]): r for r in rows}
    return [by_id[i] for i in existing if i in by_id]


def _load_lineup(store, week: dict, player: dict) -> tuple[dict | None, list[dict], list[dict], dict[str, dict]]:
    pool = store.get_week_pool(str(week["id"]))
    lineup = store.get_lineup(str(week["id"]), str(player["id"]))
    picks = store.get_lineup_picks(str(lineup["id"])) if lineup else []
    return lineup, picks, pool, _player_lookup(pool)


def _onboarding(store, player: dict) -> bool:
    if player.get("onboarding_completed_at"):
        return False
    st.markdown("### How to play")
    with st.container(border=True):
        st.markdown("**1 · Pick one at each position.**")
        st.caption("QB · RB · WR · TE · K")
    with st.container(border=True):
        st.markdown("**2 · Change your five until Sunday at 1.**")
        st.caption("Every choice autosaves as you go.")
    with st.container(border=True):
        st.markdown("**3 · Beat your friends.**")
        st.caption("Weekly finishes will feed the season standings.")
    if st.button("Let's Play", type="primary", use_container_width=True):
        updated = store.complete_onboarding(str(player["id"]))
        st.session_state.player = updated or {**player, "onboarding_completed_at": datetime.now(UTC).isoformat()}
        st.rerun()
    return True


def _week_header(week: dict) -> None:
    label = html.escape(str(week.get("label") or f"Week {week.get('nfl_week', '')}"))
    test = bool(week.get("is_demo"))
    st.markdown(
        f"""
<div class="card">
  <div class="eyebrow">{'Build test • does not affect Week 1' if test else 'Current Sunday'}</div>
  <div class="week-title">{label}</div>
  <div class="small">Locks {html.escape(et_label(week.get('locks_at')))}</div>
</div>
        """,
        unsafe_allow_html=True,
    )


def _summary_rows(picks: list[dict], pool_by_id: dict[str, dict], *, show_backups: bool = True) -> str:
    by_pos = picks_by_position(picks)
    rows = []
    for pos in POSITIONS:
        pick = by_pos.get(pos)
        starter = pool_by_id.get(str(pick.get("pool_player_id"))) if pick else None
        if starter:
            badge = _status_badge(starter)
            backup_text = ""
            if show_backups and safe_status(starter.get("availability_status")) == "QUESTIONABLE" and pick.get("emergency_pool_player_id"):
                backup = pool_by_id.get(str(pick.get("emergency_pool_player_id")))
                if backup:
                    backup_text = f'<div class="meta">Emergency: {html.escape(_display_name(backup))}</div>'
            detail = f'<div><span class="player-name">{html.escape(_display_name(starter))}</span>{badge}<div class="meta">{html.escape(_player_meta(starter))}</div>{backup_text}</div>'
        else:
            detail = '<div class="small">Not picked yet</div>'
        rows.append(f'<div class="lineup-row"><span class="position-pill">{pos}</span>{detail}</div>')
    return "".join(rows)


def _advance_builder(position: str) -> None:
    nxt = next_position(position)
    if nxt:
        st.session_state.builder_position = nxt
        st.session_state.builder_mode = "pick"
    else:
        st.session_state.builder_position = None
        st.session_state.builder_mode = "review"


def _select_starter(store, week: dict, player: dict, position: str, row: dict) -> None:
    store.save_pick(
        week_id=str(week["id"]),
        player_id=str(player["id"]),
        position=position,
        pool_player_id=str(row["id"]),
        emergency_pool_player_id=None,
    )
    if safe_status(row.get("availability_status")) == "QUESTIONABLE":
        st.session_state.builder_position = position
        st.session_state.builder_mode = "backup"
    else:
        _advance_builder(position)


def _select_backup(store, week: dict, player: dict, position: str, row: dict) -> None:
    store.set_emergency_backup(
        week_id=str(week["id"]),
        player_id=str(player["id"]),
        position=position,
        emergency_pool_player_id=str(row["id"]),
    )
    _advance_builder(position)


def _render_player_card_button(row: dict, *, key: str, selected: bool = False, disabled: bool = False) -> bool:
    status = safe_status(row.get("availability_status"))
    badge = ""
    if status == "QUESTIONABLE":
        badge = "  ⚠ QUESTIONABLE"
    elif status == "OUT":
        badge = "  OUT"
    prefix = "✓ " if selected else ""
    return st.button(
        f"{prefix}{row['player_name']}{badge}\n\n{_player_meta(row)}",
        key=key,
        disabled=disabled or status == "OUT",
        type="secondary",
        use_container_width=True,
    )


def _builder(store, week: dict, player: dict, position: str) -> None:
    lineup, picks, pool, pool_by_id = _load_lineup(store, week, player)
    by_pos = picks_by_position(picks)
    chosen, total = lineup_progress(picks)
    current = by_pos.get(position)
    current_id = str(current.get("pool_player_id")) if current else ""
    rows = _stable_order(str(player["id"]), str(week["id"]), position, position_pool(pool, position))
    mode = st.session_state.get("builder_mode", "pick")

    st.markdown(f"### Choose your {position}")
    st.caption("One tap selects. Choices autosave immediately.")

    if mode == "backup" and current:
        starter = pool_by_id.get(current_id)
        if starter and safe_status(starter.get("availability_status")) == "QUESTIONABLE":
            st.markdown(
                f'<div class="status-warn"><strong>⚠️ {_display_name(starter)} is Questionable.</strong><br>Choose one of the other {position}s as your emergency backup.</div>',
                unsafe_allow_html=True,
            )
            st.info(
                "How the emergency backup works: If your starter is ruled OUT/inactive after the 1:00 PM ET lock "
                "and does not play, your emergency backup replaces them. If your starter plays at all, your starter counts. "
                "Your backup stays private unless it activates."
            )
            backup_id = str(current.get("emergency_pool_player_id") or "")
            for row in rows:
                if str(row["id"]) == current_id:
                    continue
                if _render_player_card_button(row, key=f"backup::{position}::{row['id']}", selected=str(row["id"]) == backup_id):
                    _select_backup(store, week, player, position, row)
                    st.toast("Emergency backup saved.")
                    st.rerun()
            if st.button("Change starter", use_container_width=True):
                st.session_state.builder_mode = "pick"
                st.rerun()
            return

    for row in rows:
        if _render_player_card_button(row, key=f"starter::{position}::{row['id']}", selected=str(row["id"]) == current_id):
            try:
                _select_starter(store, week, player, position, row)
                st.toast(f"{position} saved.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

    left, right = st.columns(2)
    with left:
        prev = previous_position(position)
        if st.button("← Back", use_container_width=True, disabled=prev is None):
            st.session_state.builder_position = prev
            st.session_state.builder_mode = "pick"
            st.rerun()
    with right:
        if st.button("Review My Five", use_container_width=True, disabled=chosen < total):
            st.session_state.builder_position = None
            st.session_state.builder_mode = "review"
            st.rerun()


def _review(store, week: dict, player: dict) -> None:
    lineup, picks, pool, pool_by_id = _load_lineup(store, week, player)
    chosen, total = lineup_progress(picks)
    needs = required_backup_positions(picks, pool_by_id)

    st.markdown("### Review My Five")
    st.markdown(f'<div class="card">{_summary_rows(picks, pool_by_id)}</div>', unsafe_allow_html=True)

    by_pos = picks_by_position(picks)
    cols = st.columns(5)
    for idx, pos in enumerate(POSITIONS):
        with cols[idx]:
            if st.button(f"Change\n{pos}", key=f"change::{pos}", use_container_width=True):
                st.session_state.builder_position = pos
                st.session_state.builder_mode = "pick"
                st.rerun()

    if chosen < total:
        st.warning(f"Finish all five positions first. You have {chosen} of {total}.")
        if st.button("Continue Building", type="primary", use_container_width=True):
            st.session_state.builder_position = first_incomplete_position(picks, pool_by_id) or POSITIONS[0]
            st.session_state.builder_mode = "pick"
            st.rerun()
        return
    if needs:
        st.warning("Choose an emergency backup for: " + ", ".join(needs))
        if st.button("Fix injury backup", type="primary", use_container_width=True):
            st.session_state.builder_position = needs[0]
            st.session_state.builder_mode = "backup"
            st.rerun()
        return

    if st.button("SAVE MY LINEUP", type="primary", use_container_width=True):
        try:
            store.confirm_lineup(str(week["id"]), str(player["id"]))
            st.session_state.builder_position = None
            st.session_state.builder_mode = "home"
            st.session_state.lineup_saved_flash = True
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


def _open_home(store, week: dict, player: dict) -> None:
    lineup, picks, pool, pool_by_id = _load_lineup(store, week, player)
    chosen, total = lineup_progress(picks)
    needs = required_backup_positions(picks, pool_by_id)

    if st.session_state.pop("lineup_saved_flash", False):
        if bool(week.get("is_demo")):
            st.success("Test lineup saved. You can keep editing while the Gate 2 test week is open.")
        else:
            st.success("Lineup saved. You can make changes until Sunday at 1:00 PM ET.")

    if needs:
        st.markdown(f'<div class="status-warn"><strong>⚠️ {len(needs)} player needs attention.</strong><br>Add an emergency backup before Sunday.</div>', unsafe_allow_html=True)

    if chosen == total and not needs:
        st.markdown("### ✅ YOUR FIVE ARE READY")
        st.markdown(f'<div class="card">{_summary_rows(picks, pool_by_id)}</div>', unsafe_allow_html=True)
        if bool(week.get("is_demo")):
            st.markdown('<div class="status-test"><strong>TEST WEEK • LOCK OPEN</strong><br>Build and edit freely while testing.</div>', unsafe_allow_html=True)
        else:
            _countdown(str(week["locks_at"]), "Picks lock in")
        if st.button("EDIT LINEUP", type="primary", use_container_width=True):
            st.session_state.builder_position = None
            st.session_state.builder_mode = "review"
            st.rerun()
    else:
        st.markdown(
            f'<div class="card"><div class="eyebrow">Your lineup</div><div class="big-number">{chosen} of {total}</div><div class="small">picks complete</div></div>',
            unsafe_allow_html=True,
        )
        if bool(week.get("is_demo")):
            st.markdown('<div class="status-test"><strong>TEST WEEK • LOCK OPEN</strong><br>Build and edit freely while testing.</div>', unsafe_allow_html=True)
        else:
            _countdown(str(week["locks_at"]), "Picks lock in")
        label = "Fix Injury Backup" if needs else ("Continue Building" if chosen else "Build My Five")
        if st.button(label, type="primary", use_container_width=True):
            st.session_state.builder_position = (needs[0] if needs else first_incomplete_position(picks, pool_by_id)) or POSITIONS[0]
            st.session_state.builder_mode = "backup" if needs else "pick"
            st.rerun()


def _locked_home(store, week: dict, player: dict) -> None:
    lineup, picks, pool, pool_by_id = _load_lineup(store, week, player)
    chosen, total = lineup_progress(picks)
    st.markdown("### 🔒 Picks are locked")
    st.markdown(f'<div class="card">{_summary_rows(picks, pool_by_id)}</div>', unsafe_allow_html=True)
    if chosen < total:
        st.caption(f"You locked with {chosen} of {total} positions filled. Missing positions score 0.")
    else:
        st.caption("Your five are set for Sunday. Live scoring arrives in the next build gate.")


def render_player_game(store, player: dict) -> None:
    if _onboarding(store, player):
        return

    if "builder_mode" not in st.session_state:
        st.session_state.builder_mode = "home"
    if "builder_position" not in st.session_state:
        st.session_state.builder_position = None
    if "use_demo_week" not in st.session_state:
        st.session_state.use_demo_week = False

    real_week = store.get_real_week()
    demo_week = store.get_demo_week()
    week = demo_week if st.session_state.use_demo_week and demo_week else real_week

    if not week:
        st.info("The next Sunday week is being prepared.")
        st.caption(f"Build {APP_VERSION}")
        return

    _week_header(week)
    phase = week_phase(week)
    pool = store.get_week_pool(str(week["id"]))

    if bool(week.get("is_demo")):
        st.markdown('<div class="status-test"><strong>Gate 2 test week.</strong> Picks here are isolated and never count toward Week 1.</div>', unsafe_allow_html=True)
        if st.button("Exit Test Week", use_container_width=True):
            st.session_state.use_demo_week = False
            st.session_state.builder_mode = "home"
            st.session_state.builder_position = None
            st.rerun()
    elif phase == "upcoming":
        st.markdown("### Week 1 opens Tuesday")
        _countdown(str(week["opens_at"]), "New picks available in")
        st.caption(et_label(week.get("opens_at")))
        if demo_week and st.button("Preview Gate 2 Test Week", use_container_width=True):
            st.session_state.use_demo_week = True
            st.session_state.builder_mode = "home"
            st.session_state.builder_position = None
            st.rerun()
        return

    if phase == "open" and not pool_is_ready(pool):
        st.info("This week's player pool is being prepared. Picks will appear as soon as all five positions are ready.")
        return

    if phase == "locked":
        _locked_home(store, week, player)
        return

    mode = str(st.session_state.get("builder_mode") or "home")
    position = st.session_state.get("builder_position")
    if mode in {"pick", "backup"} and position in POSITIONS:
        _builder(store, week, player, str(position))
    elif mode == "review":
        _review(store, week, player)
    else:
        _open_home(store, week, player)
