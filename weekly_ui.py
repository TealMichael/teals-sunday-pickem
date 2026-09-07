from __future__ import annotations

import html
import random
import time
from datetime import datetime, timezone

import streamlit as st

from config import APP_VERSION
from gate4_ui import (
    maybe_render_final_celebration,
    render_gate4_demo,
    render_history,
    render_leaderboards,
    render_live_sunday,
    render_nav,
    render_profile,
)
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
    unavailable_starter_positions,
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


LINEUP_SNAPSHOT_TTL_SECONDS = 12.0


def _lineup_snapshot_key(week: dict, player: dict) -> str:
    return f"lineup_snapshot::{week['id']}::{player['id']}"


def _stash_lineup_snapshot(week: dict, player: dict, lineup: dict | None, picks: list[dict]) -> None:
    st.session_state[_lineup_snapshot_key(week, player)] = {
        "at": time.monotonic(),
        "lineup": dict(lineup) if lineup else None,
        "picks": [dict(p) for p in picks],
    }


def _merge_saved_pick(picks: list[dict], saved_pick: dict) -> list[dict]:
    position = str(saved_pick.get("position") or "")
    merged = [dict(p) for p in picks if str(p.get("position") or "") != position]
    merged.append(dict(saved_pick))
    return merged


def _load_lineup(store, week: dict, player: dict, pool: list[dict]) -> tuple[dict | None, list[dict], list[dict], dict[str, dict]]:
    key = _lineup_snapshot_key(week, player)
    snapshot = st.session_state.get(key) or {}
    age = time.monotonic() - float(snapshot.get("at") or 0.0)
    if snapshot and age <= LINEUP_SNAPSHOT_TTL_SECONDS:
        lineup = snapshot.get("lineup")
        picks = list(snapshot.get("picks") or [])
        return lineup, picks, pool, _player_lookup(pool)

    lineup, picks = store.get_lineup_state(str(week["id"]), str(player["id"]))
    _stash_lineup_snapshot(week, player, lineup, picks)
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


def _complete_builder_step(position: str) -> None:
    return_mode = st.session_state.pop("builder_return_mode", None)
    if return_mode in {"review", "home"}:
        st.session_state.builder_position = None
        st.session_state.builder_mode = return_mode
        return
    _advance_builder(position)


def _select_starter(
    store,
    week: dict,
    player: dict,
    position: str,
    row: dict,
    *,
    lineup: dict | None,
    picks: list[dict],
    pool: list[dict],
) -> None:
    saved = store.save_pick(
        week_id=str(week["id"]),
        player_id=str(player["id"]),
        position=position,
        pool_player_id=str(row["id"]),
        emergency_pool_player_id=None,
        lineup_id=str(lineup["id"]) if lineup else None,
        known_week=week,
        known_pool=pool,
    )
    resolved_lineup = lineup or {
        "id": str(saved["lineup_id"]),
        "week_id": str(week["id"]),
        "player_id": str(player["id"]),
        "confirmed_at": None,
    }
    _stash_lineup_snapshot(week, player, resolved_lineup, _merge_saved_pick(picks, saved))
    if safe_status(row.get("availability_status")) == "QUESTIONABLE":
        st.session_state.builder_position = position
        st.session_state.builder_mode = "backup"
    else:
        _complete_builder_step(position)


def _select_backup(
    store,
    week: dict,
    player: dict,
    position: str,
    row: dict,
    *,
    lineup: dict,
    picks: list[dict],
    current: dict,
    pool: list[dict],
) -> None:
    saved = store.set_emergency_backup(
        week_id=str(week["id"]),
        player_id=str(player["id"]),
        position=position,
        emergency_pool_player_id=str(row["id"]),
        starter_pool_player_id=str(current["pool_player_id"]),
        lineup_id=str(lineup["id"]),
        known_week=week,
        known_pool=pool,
    )
    _stash_lineup_snapshot(week, player, lineup, _merge_saved_pick(picks, saved))
    _complete_builder_step(position)


def _markdown_escape(value: str) -> str:
    """Escape user/provider text that is inserted into a Streamlit button label."""
    text = str(value or "")
    for ch in ("\\", "`", "*", "_", "[", "]"):
        text = text.replace(ch, "\\" + ch)
    return text


def _render_player_card_button(row: dict, *, key: str, selected: bool = False, disabled: bool = False) -> bool:
    """Render one real full-size button as the player card.

    Do not layer an invisible button over separate HTML. The visible card IS the
    Streamlit button, so every pixel of the card is a native tap target on
    desktop and mobile.
    """
    status = safe_status(row.get("availability_status"))
    safe_key = "".join(ch if ch.isalnum() or ch in "_-" else "_" for ch in key)
    state_key = "selected_" if selected else ""
    status_key = "q_" if status == "QUESTIONABLE" else ("out_" if status == "OUT" else "")
    widget_key = f"pickbtn_{state_key}{status_key}{safe_key}"

    name = _markdown_escape(str(row.get("player_name") or "—"))
    meta = _markdown_escape(_player_meta(row))
    check = "✓ " if selected else ""
    badge = " :yellow-badge[⚠ QUESTIONABLE]" if status == "QUESTIONABLE" else (" :red-badge[OUT]" if status == "OUT" else "")
    label = f"{check}**{name}**{badge}\n{meta}"

    return st.button(
        label,
        key=widget_key,
        disabled=disabled or status == "OUT",
        type="secondary",
        width="stretch",
        wrap=True,
    )


def _builder(store, week: dict, player: dict, position: str, pool: list[dict]) -> None:
    lineup, picks, pool, pool_by_id = _load_lineup(store, week, player, pool)
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
                    if lineup:
                        _select_backup(
                            store, week, player, position, row,
                            lineup=lineup, picks=picks, current=current, pool=pool,
                        )
                    st.toast("Emergency backup saved.")
                    st.rerun()
            if st.button("Change starter", use_container_width=True):
                st.session_state.builder_mode = "pick"
                st.rerun()
            return

    for row in rows:
        if _render_player_card_button(row, key=f"starter::{position}::{row['id']}", selected=str(row["id"]) == current_id):
            try:
                _select_starter(
                    store, week, player, position, row,
                    lineup=lineup, picks=picks, pool=pool,
                )
                st.toast(f"{position} saved.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

    left, right = st.columns(2)
    with left:
        return_mode = st.session_state.get("builder_return_mode")
        prev = previous_position(position)
        back_disabled = prev is None and return_mode not in {"review", "home"}
        back_label = "← Review" if return_mode == "review" else ("← Lineup" if return_mode == "home" else "← Back")
        if st.button(back_label, use_container_width=True, disabled=back_disabled):
            if return_mode in {"review", "home"}:
                st.session_state.pop("builder_return_mode", None)
                st.session_state.builder_position = None
                st.session_state.builder_mode = return_mode
            else:
                st.session_state.builder_position = prev
                st.session_state.builder_mode = "pick"
            st.rerun()
    with right:
        if st.button("Review My Five", use_container_width=True, disabled=chosen < total):
            st.session_state.builder_position = None
            st.session_state.builder_mode = "review"
            st.rerun()


def _review(store, week: dict, player: dict, pool: list[dict]) -> None:
    lineup, picks, pool, pool_by_id = _load_lineup(store, week, player, pool)
    chosen, total = lineup_progress(picks)
    needs = required_backup_positions(picks, pool_by_id)
    unavailable = unavailable_starter_positions(picks, pool_by_id)

    st.markdown("### Review My Five")
    st.markdown(f'<div class="card">{_summary_rows(picks, pool_by_id)}</div>', unsafe_allow_html=True)

    by_pos = picks_by_position(picks)
    cols = st.columns(5)
    for idx, pos in enumerate(POSITIONS):
        with cols[idx]:
            if st.button(f"Change\n{pos}", key=f"change::{pos}", use_container_width=True):
                st.session_state.builder_return_mode = "review"
                st.session_state.builder_position = pos
                st.session_state.builder_mode = "pick"
                st.rerun()

    if chosen < total:
        st.warning(f"Finish all five positions first. You have {chosen} of {total}.")
        if st.button("Continue Building", type="primary", use_container_width=True):
            st.session_state.pop("builder_return_mode", None)
            st.session_state.builder_position = first_incomplete_position(picks, pool_by_id) or POSITIONS[0]
            st.session_state.builder_mode = "pick"
            st.rerun()
        return
    if unavailable:
        st.warning("Replace the OUT player at: " + ", ".join(unavailable))
        if st.button("Replace OUT player", type="primary", use_container_width=True):
            st.session_state.builder_return_mode = "review"
            st.session_state.builder_position = unavailable[0]
            st.session_state.builder_mode = "pick"
            st.rerun()
        return
    if needs:
        st.warning("Choose a healthy emergency backup for: " + ", ".join(needs))
        if st.button("Fix injury backup", type="primary", use_container_width=True):
            st.session_state.builder_return_mode = "review"
            st.session_state.builder_position = needs[0]
            st.session_state.builder_mode = "backup"
            st.rerun()
        return

    if st.button("SAVE MY LINEUP", type="primary", use_container_width=True):
        try:
            updated_lineup = store.confirm_lineup(
                str(week["id"]),
                str(player["id"]),
                lineup_id=str(lineup["id"]) if lineup else None,
                known_week=week,
            )
            _stash_lineup_snapshot(week, player, updated_lineup, picks)
            st.session_state.builder_position = None
            st.session_state.builder_mode = "home"
            st.session_state.lineup_saved_flash = True
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


def _open_home(store, week: dict, player: dict, pool: list[dict]) -> None:
    lineup, picks, pool, pool_by_id = _load_lineup(store, week, player, pool)
    chosen, total = lineup_progress(picks)
    needs = required_backup_positions(picks, pool_by_id)
    unavailable = unavailable_starter_positions(picks, pool_by_id)

    if st.session_state.pop("lineup_saved_flash", False):
        if bool(week.get("is_demo")):
            st.success("Test lineup saved. You can keep editing while the Gate 2 test week is open.")
        else:
            st.success("Lineup saved. You can make changes until Sunday at 1:00 PM ET.")

    if unavailable:
        st.markdown(f'<div class="status-warn"><strong>🚫 {len(unavailable)} starter is OUT.</strong><br>Choose a replacement before the 1:00 PM ET lock.</div>', unsafe_allow_html=True)
    elif needs:
        st.markdown(f'<div class="status-warn"><strong>⚠️ {len(needs)} player needs attention.</strong><br>Add a healthy emergency backup before Sunday.</div>', unsafe_allow_html=True)

    if chosen == total and not needs and not unavailable:
        st.markdown("### ✅ YOUR FIVE ARE READY")
        st.markdown(f'<div class="card">{_summary_rows(picks, pool_by_id)}</div>', unsafe_allow_html=True)
        if bool(week.get("is_demo")):
            st.markdown('<div class="status-test"><strong>TEST WEEK • LOCK OPEN</strong><br>Build and edit freely while testing.</div>', unsafe_allow_html=True)
        else:
            _countdown(str(week["locks_at"]), "Picks lock in")
        if st.button("EDIT LINEUP", type="primary", use_container_width=True):
            st.session_state.pop("builder_return_mode", None)
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
        label = "Replace OUT Player" if unavailable else ("Fix Injury Backup" if needs else ("Continue Building" if chosen else "Build My Five"))
        if st.button(label, type="primary", use_container_width=True):
            if needs or unavailable:
                st.session_state.builder_return_mode = "home"
            else:
                st.session_state.pop("builder_return_mode", None)
            st.session_state.builder_position = (unavailable[0] if unavailable else (needs[0] if needs else first_incomplete_position(picks, pool_by_id))) or POSITIONS[0]
            st.session_state.builder_mode = "backup" if needs and not unavailable else "pick"
            st.rerun()


def _locked_home(store, week: dict, player: dict, pool: list[dict]) -> None:
    lineup, picks, pool, pool_by_id = _load_lineup(store, week, player, pool)
    chosen, total = lineup_progress(picks)
    st.markdown("### 🔒 Picks are locked")
    st.markdown(f'<div class="card">{_summary_rows(picks, pool_by_id)}</div>', unsafe_allow_html=True)
    if chosen < total:
        st.caption(f"You locked with {chosen} of {total} positions filled. Missing positions score 0.")
    else:
        st.caption("Your five are set for Sunday. Live scoring arrives in the next build gate.")


def render_player_game(
    store,
    player: dict,
    on_sign_out=None,
    *,
    allow_demo_week: bool = False,
    skip_onboarding: bool = False,
) -> None:
    if st.session_state.get("gate4_demo"):
        render_gate4_demo(player)
        return

    if not skip_onboarding and _onboarding(store, player):
        return

    if "builder_mode" not in st.session_state:
        st.session_state.builder_mode = "home"
    if "builder_position" not in st.session_state:
        st.session_state.builder_position = None
    if "use_demo_week" not in st.session_state:
        st.session_state.use_demo_week = False

    # Gate 2's synthetic test week is Commissioner-only in production. Any
    # stale browser session left inside the old public preview is forced back
    # to the real week before rendering the normal player app.
    if not allow_demo_week and st.session_state.get("use_demo_week"):
        st.session_state.use_demo_week = False
        st.session_state.builder_mode = "home"
        st.session_state.builder_position = None
        st.session_state.pop("builder_return_mode", None)

    real_week = store.get_real_week()
    demo_week = store.get_demo_week() if allow_demo_week else None
    week = demo_week if allow_demo_week and st.session_state.use_demo_week and demo_week else real_week

    if not week:
        st.info("The next Sunday week is being prepared.")
        st.caption(f"Build {APP_VERSION}")
        return

    phase = week_phase(week)

    # Gate 2's isolated test week remains a focused lineup-builder test. The
    # normal app gets the four-tab Gate 4 navigation.
    if not bool(week.get("is_demo")):
        tab = render_nav()
        if tab == "🏆 Season":
            render_leaderboards(store, week, player, phase)
            return
        if tab == "🕘 History":
            render_history(store, int(week.get("season") or 2026))
            return
        if tab == "👤 Profile":
            render_profile(store, player, int(week.get("season") or 2026), on_sign_out)
            return

    _week_header(week)

    if bool(week.get("is_demo")):
        st.markdown('<div class="status-test"><strong>Gate 2 test week.</strong> Picks here are isolated and never count toward Week 1.</div>', unsafe_allow_html=True)
        if st.button("Exit Gate 2 Test Week", use_container_width=True):
            st.session_state.use_demo_week = False
            st.session_state.builder_mode = "home"
            st.session_state.builder_position = None
            st.session_state.pop("builder_return_mode", None)
            if st.session_state.get("commish"):
                st.session_state.gate2_demo = False
                st.session_state.pop("gate2_demo_player_id", None)
            st.rerun()
    elif phase == "upcoming":
        label = str(week.get("label") or f"Week {week.get('nfl_week', '')}")
        st.markdown(f"### {label} opens Tuesday")
        _countdown(str(week["opens_at"]), "New picks available in")
        st.caption(et_label(week.get("opens_at")))
        return

    if phase == "locked" and not bool(week.get("is_demo")):
        maybe_render_final_celebration(store, week, player)
        render_live_sunday(store, week, player, show_storylines=True)
        return

    pool = store.get_week_pool(str(week["id"]), visible_only=True)

    if phase == "open" and not pool_is_ready(pool):
        st.info("This week's player pool is being prepared. Picks will appear as soon as all five positions are ready.")
        return

    if phase == "locked":
        _locked_home(store, week, player, pool)
        return

    mode = str(st.session_state.get("builder_mode") or "home")
    position = st.session_state.get("builder_position")
    if mode in {"pick", "backup"} and position in POSITIONS:
        _builder(store, week, player, str(position), pool)
    elif mode == "review":
        _review(store, week, player, pool)
    else:
        _open_home(store, week, player, pool)

