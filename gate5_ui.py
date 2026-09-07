from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import streamlit as st

from gate5 import (
    CommissionerError,
    clear_score_override,
    finalize_week_now,
    generate_pool_again,
    pool_override_preview,
    refresh_nfl_now,
    replace_pool_player,
    reset_player_pin,
    set_score_override,
    week_snapshot,
)
from weekly import POSITIONS, et_label, parse_timestamp

UTC = timezone.utc
GATE5_UI_SCHEMA_VERSION = 1


def _status_label(row: dict[str, Any]) -> str:
    count = int(row.get("pick_count") or 0)
    if bool(row.get("confirmed")) and count == 5:
        return "READY"
    if count == 0:
        return "NOT STARTED"
    return f"INCOMPLETE ({count}/5)"


def _ago(value: str | None) -> str:
    dt = parse_timestamp(value)
    if not dt:
        return "Never"
    seconds = max(0, int((datetime.now(UTC) - dt).total_seconds()))
    if seconds < 60:
        return "Just now"
    if seconds < 3600:
        return f"{seconds // 60} min ago"
    if seconds < 86400:
        return f"{seconds // 3600} hr ago"
    return f"{seconds // 86400} d ago"


def _set_flash(message: str, *, kind: str = "success") -> None:
    st.session_state["g5_flash"] = {"message": message, "kind": kind}


def _render_flash() -> None:
    flash = st.session_state.pop("g5_flash", None)
    if not flash:
        return
    message = str(flash.get("message") or "").strip()
    kind = str(flash.get("kind") or "success")
    if not message:
        return
    if kind == "error":
        st.error(message)
    elif kind == "warning":
        st.warning(message)
    elif kind == "info":
        st.info(message)
    else:
        st.success(message)


def _render_week_overview(store, week: dict[str, Any]) -> None:
    snapshot = week_snapshot(store, week)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Players", snapshot["registered"])
    c2.metric("Lineups ready", snapshot["ready"])
    c3.metric("Need lineup", snapshot["incomplete"])
    c4.metric("NFL data", str(week.get("data_status") or "WAITING"))

    st.caption(
        f"Locks {et_label(week.get('locks_at'))} • Last NFL refresh: {_ago(week.get('last_data_refresh_at'))}"
    )

    now = datetime.now(UTC)
    opens = parse_timestamp(week.get("opens_at"))
    needs = snapshot.get("needs_attention") or []
    if opens and now < opens:
        st.info(f"Lineups open {et_label(opens)}. No player action is needed yet.")
    elif needs:
        with st.expander(f"Needs attention • {len(needs)} player{'s' if len(needs) != 1 else ''}"):
            for row in needs:
                st.write(f"{row.get('emoji') or '🏈'} **{row.get('nickname')}** — {_status_label(row)}")
    else:
        st.success("Everyone has a complete saved lineup.")

    st.markdown("#### NFL Data")
    r1, r2 = st.columns([2, 1])
    with r1:
        st.caption("Refreshes schedule/player status now. After lock it also runs the production live-score path.")
        if st.button("Refresh NFL Data Now", type="primary", use_container_width=True, key="g5_refresh_nfl"):
            try:
                # Toast feedback avoids inserting a spinner into the page layout.
                # Streamlit keeps the prior widget tree visible while a long action runs;
                # adding a spinner here made the Week controls appear duplicated/ghosted.
                st.toast("Refreshing NFL data…")
                result = refresh_nfl_now(store, week)
                st.session_state.g5_last_refresh = result
                _set_flash("NFL data refresh completed. The Week screen now shows the latest stored status and refresh time.")
                st.rerun()
            except Exception as exc:
                st.error(f"NFL refresh failed: {exc}")
    with r2:
        if st.button("Check database", use_container_width=True, key="g5_db_check"):
            st.toast("Database connected." if store.healthcheck() else "Database check failed.")

    st.markdown("#### Week Controls")
    lock = parse_timestamp(week.get("locks_at"))
    published = bool(week.get("published_at"))
    can_generate = bool(not published and opens and now >= opens)
    can_finalize = bool(lock and now >= lock)

    wc1, wc2 = st.columns(2)
    with wc1:
        st.caption("Use only if Tuesday's automatic player-pool publication failed.")
        if st.button(
            "Generate Again",
            disabled=not can_generate,
            use_container_width=True,
            key="g5_generate_again",
        ):
            try:
                with st.spinner("Rebuilding the weekly player pool…"):
                    generate_pool_again(store, week)
                _set_flash("Weekly pool generated and published successfully.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
        if not published and not can_generate:
            st.caption("Available after the scheduled Tuesday opening time.")
        elif published:
            st.caption("Already published. Corrections belong in Player Pool Override.")

    with wc2:
        st.caption("Runs the same final reconciliation used Monday morning. It refuses to finalize unsettled games.")
        if st.button(
            "Reconcile / Finalize Now",
            disabled=not can_finalize,
            use_container_width=True,
            key="g5_finalize_now",
        ):
            try:
                with st.spinner("Reconciling official stats…"):
                    result = finalize_week_now(store, week)
                _set_flash(f"Week finalized. {int(result.get('results') or 0)} result rows archived.")
                st.rerun()
            except Exception as exc:
                st.error(f"Finalization deferred: {exc}")
        if not can_finalize:
            st.caption("Available after the universal Sunday 1:00 PM ET lock.")

    runs = store.get_recent_data_runs(week_id=str(week["id"]), limit=10)
    if runs:
        with st.expander("Recent NFL / Commissioner activity"):
            display = []
            for row in runs:
                display.append({
                    "When": _ago(row.get("completed_at") or row.get("started_at")),
                    "Run": str(row.get("run_type") or "").replace("_", " ").title(),
                    "Result": "PASS" if row.get("success") is True else ("FAIL" if row.get("success") is False else "RUNNING"),
                    "Message": row.get("message") or "",
                })
            st.dataframe(display, hide_index=True, use_container_width=True)


def _render_players(store, week: dict[str, Any], pin_pepper: str) -> None:
    statuses = week_snapshot(store, week).get("statuses") or []
    st.markdown("#### Players & PINs")
    st.caption("PINs are never readable. A reset creates a replacement PIN and signs that player out on every remembered device.")

    display = []
    for row in statuses:
        display.append({
            "Player": f"{row.get('emoji') or '🏈'} {row.get('nickname')}",
            "This week": _status_label(row),
            "Last seen": _ago(row.get("last_seen_at")),
        })
    if display:
        st.dataframe(display, hide_index=True, use_container_width=True)

    options = {f"{row.get('emoji') or '🏈'} {row.get('nickname')}": row for row in statuses}
    selected_label = st.selectbox("Player to reset", list(options), key="g5_pin_player") if options else None
    selected = options.get(selected_label) if selected_label else None
    if selected:
        with st.form("g5_pin_reset_form", clear_on_submit=True):
            new_pin = st.text_input("New 4-digit PIN", type="password", max_chars=4)
            confirm = st.text_input("Confirm new PIN", type="password", max_chars=4)
            submitted = st.form_submit_button("Reset Player PIN", type="primary", use_container_width=True)
        if submitted:
            try:
                player = reset_player_pin(
                    store,
                    player_id=str(selected["id"]),
                    new_pin=new_pin,
                    pin_confirm=confirm,
                    pin_pepper=pin_pepper,
                )
                st.success(f"PIN reset for {player.get('nickname')}. Their remembered-device sessions were revoked.")
            except Exception as exc:
                st.error(str(exc))


def _pool_option(row: dict[str, Any]) -> str:
    status = str(row.get("availability_status") or "HEALTHY")
    suffix = ""
    if status != "HEALTHY":
        suffix = f" • {status}"
    return f"#{int(row.get('slot_rank') or 0)} {row.get('player_name')} • {row.get('team_abbr')}{suffix}"


def _render_corrections(store, week: dict[str, Any]) -> None:
    st.markdown("#### Emergency Player Pool Override")
    st.caption("Use only when the published five are clearly wrong. Any affected starter pick is removed so that player must choose again.")
    pool = store.get_full_week_pool(str(week["id"]))
    if not week.get("published_at"):
        st.info("The weekly player pool has not been published yet.")
    else:
        lock = parse_timestamp(week.get("locks_at"))
        after_lock = bool(lock and datetime.now(UTC) >= lock)
        position = st.segmented_control(
            "Position",
            list(POSITIONS),
            default="QB",
            key="g5_pool_position",
            width="stretch",
        ) or "QB"
        pos_rows = sorted([r for r in pool if str(r.get("position")) == position], key=lambda r: int(r.get("slot_rank") or 99))
        visible = [r for r in pos_rows if r.get("is_visible")]
        hidden = [r for r in pos_rows if not r.get("is_visible") and str(r.get("availability_status") or "HEALTHY") != "OUT" and bool(r.get("schedule_eligible", True))]
        visible_map = {_pool_option(r): r for r in visible}
        hidden_map = {_pool_option(r): r for r in hidden}
        oc1, oc2 = st.columns(2)
        with oc1:
            outgoing_label = st.selectbox("Replace", list(visible_map), key="g5_pool_out") if visible_map else None
        with oc2:
            replacement_label = st.selectbox("With", list(hidden_map), key="g5_pool_in") if hidden_map else None
        outgoing = visible_map.get(outgoing_label) if outgoing_label else None
        replacement = hidden_map.get(replacement_label) if replacement_label else None
        impact = None
        if outgoing:
            try:
                impact = pool_override_preview(store, week, str(outgoing["id"]))
            except Exception as exc:
                st.error(str(exc))
        if impact:
            affected = int(impact.get("affected_lineups") or 0)
            names = impact.get("affected_nicknames") or []
            if affected:
                st.warning(f"{affected} lineup{'s' if affected != 1 else ''} affected: " + ", ".join(names))
            else:
                st.info("No current lineup uses this player.")
        reason = st.text_input("Reason for override", placeholder="Example: wrong player in Tuesday pool", key="g5_pool_reason")
        confirm = st.checkbox("I understand affected players will need to choose again.", key="g5_pool_confirm")
        if st.button(
            "Replace Player",
            type="primary",
            use_container_width=True,
            disabled=after_lock or not outgoing or not replacement or not confirm,
            key="g5_pool_replace",
        ):
            try:
                result = replace_pool_player(
                    store,
                    week,
                    outgoing_pool_id=str(outgoing["id"]),
                    replacement_pool_id=str(replacement["id"]),
                    reason=reason,
                )
                _set_flash(f"{result['outgoing_name']} replaced by {result['replacement_name']}.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
        if after_lock:
            st.caption("Locked: Commissioner pool changes are disabled after Sunday at 1:00 PM ET.")

    st.markdown("---")
    st.markdown("#### Manual Score Override")
    st.caption("A manual value stays authoritative through automatic refreshes until you clear it.")
    if not week.get("published_at"):
        st.info("Score correction tools appear after Tuesday’s pool publishes; applying a correction remains locked until Sunday at 1:00 PM ET.")
        return
    lock = parse_timestamp(week.get("locks_at"))
    after_lock = bool(lock and datetime.now(UTC) >= lock)
    visible_pool = [r for r in store.get_full_week_pool(str(week["id"])) if r.get("is_visible")]
    score_map = {
        f"{r.get('position')} • {r.get('player_name')} • {r.get('team_abbr')}": r
        for r in visible_pool
    }
    score_label = st.selectbox("Player score", list(score_map), key="g5_score_player") if score_map else None
    player = score_map.get(score_label) if score_label else None
    if player:
        provider_score = player.get("score_total") if player.get("manual_score_override") is None else None
        current_manual = player.get("manual_score_override")
        m1, m2, m3 = st.columns(3)
        m1.metric("Current score", f"{float(player.get('score_total') or 0):.2f}")
        m2.metric("Status", str(player.get("score_status") or "SCHEDULED"))
        m3.metric("Manual override", "None" if current_manual is None else f"{float(current_manual):.2f}")
        default_score = float(current_manual if current_manual is not None else (player.get("score_total") or 0))
        corrected = st.number_input("Correct score", value=default_score, step=0.1, format="%.2f", key="g5_score_value")
        note = st.text_input("Correction note", placeholder="Example: provider missed return TD", key="g5_score_note")
        sc1, sc2 = st.columns(2)
        with sc1:
            if st.button("Apply Override", type="primary", use_container_width=True, disabled=not after_lock, key="g5_score_apply"):
                try:
                    set_score_override(store, week, pool_player_id=str(player["id"]), score=float(corrected), note=note)
                    _set_flash("Manual score override applied. Automatic refreshes will not overwrite it until you clear the override.")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))
        with sc2:
            if st.button("Clear Override", use_container_width=True, disabled=not after_lock or current_manual is None, key="g5_score_clear"):
                try:
                    clear_score_override(store, week, pool_player_id=str(player["id"]))
                    _set_flash("Manual override cleared; provider scoring is active again.")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))
        if not after_lock:
            st.caption("Score corrections unlock at Sunday 1:00 PM ET.")
        elif str(week.get("data_status") or "").upper() == "FINAL":
            st.caption("Because this week is FINAL, applying or clearing an override also rebuilds the archived weekly standings.")


def _render_diagnostics(store) -> None:
    st.markdown("#### Diagnostics & Demos")
    d1, d2 = st.columns(2)
    with d1:
        if st.button("Run Gate 3 Data Check", use_container_width=True, key="g5_gate3_data"):
            try:
                from nfl_sync import gate3_diagnostic
                with st.spinner("Checking schedule, players, injuries, and Week 1 ranking…"):
                    st.session_state.gate3_diag = gate3_diagnostic(store)
                st.toast("Gate 3 data check passed.")
            except Exception as exc:
                st.session_state.gate3_diag = None
                st.error(f"Gate 3 data check failed: {exc}")
    with d2:
        if st.button("Run Gate 3 Scoring Test", use_container_width=True, key="g5_gate3_score"):
            try:
                from scoring_diagnostic import run_scoring_diagnostic
                with st.spinner("Testing scoring math, Supabase persistence, Week 1 isolation, and cleanup…"):
                    st.session_state.gate3_scoring_diag = run_scoring_diagnostic(store)
                st.toast("Gate 3 scoring test passed.")
            except Exception as exc:
                st.session_state.gate3_scoring_diag = None
                st.error(f"Gate 3 scoring test failed: {exc}")

    if st.button("Preview Gate 4 Live Sunday Demo", use_container_width=True, key="g5_gate4_demo"):
        st.session_state.gate4_demo = True
        st.session_state.gate4_demo_phase = "live"
        st.session_state.gate4_tab = "🏈 Sunday"
        st.session_state.pop("gate4_nav", None)
        st.session_state.pop("gate4_nav_fallback", None)
        st.session_state.pop("gate4_detail_player_id", None)
        st.rerun()

    replay_col1, replay_col2 = st.columns(2)
    with replay_col1:
        st.link_button(
            "Open Gate 3.5 Replay Runner",
            "https://github.com/TealMichael/teals-sunday-pickem/actions/workflows/nfl-refresh.yml",
            use_container_width=True,
        )
    with replay_col2:
        if st.button("Refresh Gate 3.5 Result", use_container_width=True, key="g5_gate35_result"):
            replay_run = store.last_successful_run("preseason_replay")
            if replay_run:
                metadata = replay_run.get("metadata") or {}
                st.session_state.gate35_replay_diag = {
                    "success": True,
                    "matchup": metadata.get("matchup"),
                    "provider_event_id": metadata.get("provider_event_id"),
                    "boxscore_pass": bool(metadata.get("anchor_pass")),
                    "anchor_pass": bool(metadata.get("anchor_pass")),
                    "database_pass": bool(metadata.get("database_pass")),
                    "week1_isolation_pass": bool(metadata.get("week1_isolation_pass")),
                    "cleanup_pass": bool(metadata.get("cleanup_pass")),
                    "rows": metadata.get("rows") or [],
                    "anchors": metadata.get("anchors") or [],
                }
                st.toast("Latest Gate 3.5 replay result loaded.")
            else:
                st.info("No successful Gate 3.5 replay has been recorded yet.")

    diag = st.session_state.get("gate3_diag")
    if diag:
        with st.expander("Gate 3 data-check result", expanded=False):
            st.metric("Eligible Sunday games", int(diag.get("eligible_games") or 0))
            preview = diag.get("visible_preview") or {}
            for position in POSITIONS:
                st.markdown(f"**{position}:** " + " • ".join(preview.get(position) or []))

    scoring_diag = st.session_state.get("gate3_scoring_diag")
    if scoring_diag:
        with st.expander("Gate 3 scoring-test result", expanded=False):
            st.success("PASS — scoring math, Supabase round trip, Week 1 isolation, and cleanup.")

    replay_diag = st.session_state.get("gate35_replay_diag")
    if replay_diag:
        with st.expander("Gate 3.5 real-box-score result", expanded=False):
            st.success("PASS — real box score → parser → scoring → Supabase → cleanup.")
            st.caption(str(replay_diag.get("matchup") or "2026 preseason replay"))


def render_commissioner_dashboard(store, *, pin_pepper: str) -> None:
    st.markdown("### Commissioner • Gate 5")
    st.success("Commissioner controls are live. Player lineups remain protected by the universal Sunday 1:00 PM ET database lock.")
    _render_flash()

    week = store.get_real_week()
    if not week:
        st.error("No current real week is available.")
        if st.button("Exit Commissioner", use_container_width=True):
            st.session_state.commish = False
            st.rerun()
        return
    week = store.get_week_by_season_week(int(week["season"]), int(week["nfl_week"])) or week
    st.caption(
        f"{week.get('label', 'Current week')} • {week.get('data_status', 'WAITING')}"
        + (f" • {week.get('data_message')}" if week.get("data_message") else "")
    )

    top1, top2 = st.columns([3, 1])
    with top1:
        tool = st.segmented_control(
            "Commissioner tool",
            ["Week", "Players", "Corrections", "Diagnostics"],
            default="Week",
            key="g5_tool",
            width="stretch",
            label_visibility="collapsed",
        ) or "Week"
    with top2:
        if st.button("Exit Commissioner", use_container_width=True, key="g5_exit"):
            st.session_state.commish = False
            st.session_state.pop("g5_tool", None)
            st.rerun()

    if tool == "Week":
        _render_week_overview(store, week)
    elif tool == "Players":
        _render_players(store, week, pin_pepper)
    elif tool == "Corrections":
        _render_corrections(store, week)
    else:
        _render_diagnostics(store)
