from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

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
from gate6_ui import render_launch_readiness

UTC = timezone.utc
GATE5_UI_SCHEMA_VERSION = 4


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
    st.caption("Refreshes schedule/player status now. After lock it also runs the production live-score path.")
    if st.button("Refresh NFL Data Now", type="primary", use_container_width=True, key="g5_refresh_nfl"):
        try:
            # Toast feedback avoids inserting a spinner into the page layout.
            st.toast("Refreshing NFL data…")
            result = refresh_nfl_now(store, week)
            st.session_state.g5_last_refresh = result
            _set_flash("NFL data refresh completed. The Week screen now shows the latest stored status and refresh time.")
            st.rerun()
        except Exception as exc:
            st.error(f"NFL refresh failed: {exc}")

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


def _render_live_dress_rehearsal(store, week: dict[str, Any]) -> None:
    with st.expander("Wednesday Live Game Dress Rehearsal", expanded=False):
        st.caption(
            "Commissioner-only and read-only. This uses the same nflverse schedule, ESPN CDN box-score parser, "
            "team/name matching, and Pick'em scoring formula as production live scoring. It does not write Week 1 scores, lineups, standings, or NFL data."
        )

        if st.button("Load / refresh current-week games", use_container_width=True, key="g5_live_test_load_games"):
            try:
                from live_dress_rehearsal import discover_rehearsal_games

                with st.spinner("Loading the real NFL schedule for this week…"):
                    st.session_state.g5_live_test_games = discover_rehearsal_games(
                        season=int(week["season"]),
                        nfl_week=int(week["nfl_week"]),
                    )
                st.toast("Current-week games loaded.")
            except Exception as exc:
                st.session_state.g5_live_test_games = []
                st.error(f"Could not load the current-week games: {exc}")

        games = st.session_state.get("g5_live_test_games") or []
        if not games:
            st.info("Load the current-week games first. On Wednesday, choose the Wednesday night matchup and run the test after kickoff.")
            return

        labels = [str(row.get("label") or row.get("provider_event_id")) for row in games]
        by_label = {str(row.get("label") or row.get("provider_event_id")): row for row in games}
        selected_label = st.selectbox("Game to test", labels, key="g5_live_test_game")
        selected = by_label[selected_label]

        run_col, clear_col = st.columns([3, 1])
        with run_col:
            run_now = st.button("Run Live Game Test Now", type="primary", use_container_width=True, key="g5_live_test_run")
        with clear_col:
            if st.button("Clear", use_container_width=True, key="g5_live_test_clear"):
                st.session_state.pop("g5_live_test_result", None)
                st.session_state.pop("g5_live_test_previous", None)
                st.rerun()

        if run_now:
            try:
                from live_dress_rehearsal import compare_rehearsal_snapshots, run_live_game_rehearsal

                previous = st.session_state.get("g5_live_test_result")
                with st.spinner("Reading the real game feed and running the production parser/scorer…"):
                    result = run_live_game_rehearsal(
                        store,
                        season=int(week["season"]),
                        nfl_week=int(week["nfl_week"]),
                        provider_event_id=str(selected.get("provider_event_id") or ""),
                    )
                result["comparison"] = compare_rehearsal_snapshots(previous, result)
                if previous:
                    st.session_state.g5_live_test_previous = previous
                st.session_state.g5_live_test_result = result
                st.toast("Live-game test complete. No Week 1 data was changed.")
            except Exception as exc:
                st.error(f"Live-game test failed: {exc}")

        result = st.session_state.get("g5_live_test_result")
        if not result:
            st.caption("Run this several times during the game. We want to see the status and player stat lines change between snapshots.")
            return

        if str(result.get("provider_event_id")) != str(selected.get("provider_event_id")):
            st.info("The result below is from a different game selection. Run the test again for the selected game.")

        live_status = str(result.get("espn_status") or "SCHEDULED")
        active_rows = int(result.get("active_stat_rows") or 0)
        fantasy_rows = int(result.get("fantasy_rows") or 0)
        rate = float(result.get("match_rate") or 0.0) * 100.0
        if live_status in {"LIVE", "FINAL"} and active_rows > 0:
            st.success("READ-ONLY LIVE PASS — real schedule → ESPN box score → parser → identity match → Pick'em scoring.")
        elif live_status == "SCHEDULED":
            st.info("CONNECTION PASS — the real game was found and ESPN responded. Re-run after kickoff to verify moving live stats and scoring.")
        else:
            st.warning("The game feed is live, but no fantasy-scoring stat rows were parsed yet. Re-run after a few plays.")
        st.caption(f"{result.get('matchup')} • tested {_ago(result.get('fetched_at'))}")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Game", live_status)
        c2.metric("Parsed rows", int(result.get("parsed_rows") or 0))
        c3.metric("Active scoring rows", active_rows)
        c4.metric("Exact production-key matches", f"{rate:.0f}%" if active_rows else "—")

        if live_status in {"LIVE", "FINAL"} and active_rows and rate < 85.0:
            st.warning("Some live scoring rows do not match cached players by the exact team+name key production uses. The rows are still shown so we can diagnose name/team differences before Sunday.")

        score_bits = []
        if result.get("away_team"):
            score_bits.append(f"{result.get('away_team')} {result.get('away_score') if result.get('away_score') is not None else '—'}")
        if result.get("home_team"):
            score_bits.append(f"{result.get('home_team')} {result.get('home_score') if result.get('home_score') is not None else '—'}")
        game_detail = " • ".join(score_bits)
        if result.get("period") or result.get("clock"):
            game_detail += f" • Q{result.get('period') or '?'} {result.get('clock') or ''}"
        if game_detail:
            st.caption(game_detail)

        comparison = result.get("comparison") or {}
        if st.session_state.get("g5_live_test_previous"):
            changed = int(comparison.get("changed_players") or 0)
            if changed:
                st.info(f"Since the previous snapshot: {changed} player stat line(s) changed. That is exactly what we want to see during live play.")
            elif str(result.get("espn_status")) == "LIVE":
                st.warning("No player stat lines changed since the previous snapshot yet. Try another refresh after the next few plays.")
            else:
                st.caption("No player stat changes since the previous snapshot.")

        unmatched = result.get("unmatched_diagnostics") or []
        if unmatched:
            with st.expander(f"Why unmatched? • {len(unmatched)} live scoring row(s)", expanded=True):
                st.caption(
                    "Read-only identity diagnosis. This compares ESPN live names/teams with the cached Sleeper roster; "
                    "it does not change production matching or any Week 1 data."
                )
                cache_bits = [f"{int(result.get('cached_player_count') or 0)} cached fantasy players"]
                if result.get("cache_latest_synced_at"):
                    cache_bits.append(f"cache last synced {_ago(result.get('cache_latest_synced_at'))}")
                st.caption(" • ".join(cache_bits))
                st.info(
                    "A miss here only becomes a Sunday scoring risk if one of the actual Sunday pool players has the same identity mismatch. "
                    "Wednesday players are being used to diagnose the matching rule, not to change the Week 1 pool."
                )

                diag_rows = []
                for item in unmatched:
                    candidate = item.get("top_candidate") or {}
                    candidate_name = str(candidate.get("full_name") or "—")
                    candidate_team = str(candidate.get("team_abbr") or "—")
                    candidate_pos = str(candidate.get("position") or "—")
                    similarity = candidate.get("similarity")
                    candidate_text = f"{candidate_name} • {candidate_team} • {candidate_pos}" if candidate_name != "—" else "—"
                    if similarity is not None and candidate_name != "—":
                        candidate_text += f" • {float(similarity) * 100:.0f}% name match"
                    diag_rows.append({
                        "ESPN player": item.get("player_name"),
                        "ESPN team": item.get("team_abbr"),
                        "Role": item.get("position"),
                        "ESPN ID": item.get("espn_player_id") or "—",
                        "Why exact key missed": item.get("reason"),
                        "Best cached candidate": candidate_text,
                        "Scoring stats": item.get("stat_formula"),
                    })
                st.dataframe(diag_rows, use_container_width=True, hide_index=True)

                with st.expander("Candidate details", expanded=False):
                    for item in unmatched:
                        candidates = item.get("candidates") or []
                        st.markdown(f"**{item.get('player_name')} ({item.get('team_abbr')})** — {item.get('reason')}")
                        if not candidates:
                            st.caption("No plausible cached candidate found.")
                            continue
                        for candidate in candidates:
                            st.caption(
                                f"{candidate.get('full_name')} • {candidate.get('team_abbr') or '—'} • {candidate.get('position') or '—'} "
                                f"• Sleeper {candidate.get('sleeper_player_id') or '—'} • {float(candidate.get('similarity') or 0) * 100:.0f}% name match"
                            )

        samples = result.get("samples") or {}
        if samples:
            st.markdown("##### Live scoring samples")
            for position in POSITIONS:
                row = samples.get(position)
                if not row:
                    continue
                match_mark = "✓ matched" if row.get("matched_cached_player") else "⚠ unmatched"
                st.markdown(
                    f"**{position} — {row.get('player_name')} ({row.get('team_abbr')}) — {row.get('display_points')} pts**  \n"
                    f"{row.get('stat_formula')}  \n"
                    f"`{row.get('points_formula')}` • {match_mark}"
                )

        category_samples = result.get("category_samples") or {}
        if category_samples:
            st.markdown("##### Stat-category proof")
            st.caption("This section ignores missing ESPN position labels so we can prove each live stat category is arriving and scoring.")
            for category in ("Passing", "Rushing", "Receiving", "Kicking"):
                row = category_samples.get(category)
                if not row:
                    continue
                match_mark = "✓ exact production key" if row.get("matched_cached_player") else f"⚠ {row.get('identity_resolution') or 'identity unresolved'}"
                st.markdown(
                    f"**{category} — {row.get('player_name')} ({row.get('team_abbr')}) — {row.get('display_points')} pts**  \n"
                    f"{row.get('stat_formula')}  \n"
                    f"`{row.get('points_formula')}` • {match_mark}"
                )

        with st.expander("All parsed live scoring rows", expanded=False):
            table_rows = []
            for row in result.get("rows") or []:
                table_rows.append({
                    "Pos": row.get("position"),
                    "Player": row.get("player_name"),
                    "Team": row.get("team_abbr"),
                    "Pts": row.get("display_points"),
                    "Exact key": "Yes" if row.get("matched_cached_player") else "No",
                    "Identity": row.get("identity_resolution"),
                    "Scoring stats": row.get("stat_formula"),
                })
            if table_rows:
                st.dataframe(table_rows, use_container_width=True, hide_index=True)
            else:
                st.caption("No Pick’em-relevant scoring rows have appeared in the box score yet.")

        st.caption(
            "Wednesday success target: the game moves to LIVE, parsed rows appear, identity matching stays healthy, "
            "fantasy totals update across multiple snapshots, and the raw scoring ingredients agree with the TV/box score."
        )


def _render_clock(store, week: dict[str, Any]) -> None:
    from clock_broadcast import new_clock_token, refresh_clock_snapshot

    st.markdown("#### 🏈 Sunday Clock")
    st.caption("Your Sunday broadcast layer for the AWTRIX clock. If you leave every message blank, the automatic Pick'em feed still runs by itself.")

    if not store.clock_schema_available():
        st.warning("Sunday Clock setup is not installed yet. Run db/006_sunday_clock.sql once in the Supabase SQL Editor, then reload this tab.")
        script_path = Path(__file__).with_name("awtrix") / "PickemSunday.ax"
        if script_path.exists():
            st.download_button("Download PickemSunday.ax", script_path.read_text("utf-8"), file_name="PickemSunday.ax", mime="text/plain", use_container_width=True)
        return

    settings = store.get_clock_week_settings(str(week["id"]))
    st.markdown("##### This Sunday's messages")
    st.caption("These belong only to this NFL week and never carry into the next one automatically.")
    with st.form("g5_clock_messages"):
        welcome_enabled = st.checkbox("Use Welcome / Who's Here", value=bool(settings.get("welcome_enabled")))
        welcome_text = st.text_area(
            "Welcome / Who's Here",
            value=str(settings.get("welcome_text") or ""),
            placeholder="Welcome! Mike, Jenny, Alan, Will, Jonas…",
            max_chars=240,
        )
        party_enabled = st.checkbox("Use Food or Party Message", value=bool(settings.get("party_enabled")))
        party_text = st.text_area(
            "Food or Party Message",
            value=str(settings.get("party_text") or ""),
            placeholder="Wings at halftime • Pizza around 4:00",
            max_chars=240,
        )
        custom_enabled = st.checkbox("Use Custom Message", value=bool(settings.get("custom_enabled")))
        custom_text = st.text_area(
            "Custom Message",
            value=str(settings.get("custom_text") or ""),
            placeholder="House rule: bad fantasy decisions may be mocked publicly.",
            max_chars=240,
        )
        save_messages = st.form_submit_button("Save Sunday Clock Messages", type="primary", use_container_width=True)
    if save_messages:
        try:
            store.save_clock_week_settings(
                str(week["id"]),
                welcome_enabled=welcome_enabled,
                welcome_text=welcome_text,
                party_enabled=party_enabled,
                party_text=party_text,
                custom_enabled=custom_enabled,
                custom_text=custom_text,
            )
            refresh_clock_snapshot(store, week)
            _set_flash("Sunday Clock messages saved for this week.")
            st.rerun()
        except Exception as exc:
            st.error(f"Clock messages could not be saved: {exc}")

    st.markdown("##### Automatic Sunday broadcast")
    st.caption("No setup needed each week. Before 1 PM the clock keeps picks private. After lock, it rotates app-owned updates without calculating anything on the clock itself.")
    st.markdown(
        "**Every ~15 min:** full current-week Pick'em standings  \n"
        "**Every ~30 min:** all live NFL scores  \n"
        "**Every ~30 min:** Player Update from this week's 25-player pool only  \n"
        "**Starting Week 2, every ~30 min:** full season standings  \n"
        "**Manual slots:** enabled Welcome / Party / Custom messages rotate about every 30 min"
    )

    snap_row = store.get_clock_snapshot(str(week["id"]))
    if not snap_row:
        payload = refresh_clock_snapshot(store, week) or {}
        snap_row = {"payload": payload, "updated_at": payload.get("generated_at")}
    payload = dict((snap_row or {}).get("payload") or {})
    if st.button("Refresh Clock Preview", use_container_width=True, key="g5_clock_preview_refresh"):
        payload = refresh_clock_snapshot(store, week) or payload
        st.rerun()

    with st.expander("Preview automatic rotation", expanded=False):
        st.caption(f"Broadcast snapshot updated {_ago((snap_row or {}).get('updated_at'))}.")
        previews = [
            ("Before lock", payload.get("readiness")),
            ("Weekly standings", payload.get("weekly")),
            ("Live NFL scores", payload.get("live_games")),
            ("Season standings", payload.get("season_text")),
            ("Weekly champion", payload.get("champion")),
        ]
        for label, text in previews:
            if text:
                st.markdown(f"**{label}**  \n{text}")
        player_updates = list(payload.get("player_updates") or [])
        if player_updates:
            st.markdown("**Player Update samples**")
            for text in player_updates[:3]:
                st.write(text)
        pulses = list(payload.get("pulses") or [])
        if pulses:
            st.markdown("**Pick'em Pulse samples**")
            for text in pulses[:3]:
                st.write(text)

    st.markdown("##### Physical clock")
    token_status = store.get_clock_token_status()
    if token_status:
        st.success(f"Scoped clock token configured • ends in {token_status.get('token_hint') or '------'}")
        st.caption(
            f"Last clock check-in: {_ago(token_status.get('last_seen_at'))} • "
            f"Last display acknowledgement: {_ago(token_status.get('last_ack_at'))}"
        )
    else:
        st.info("No scoped Pick'em clock token has been created yet.")

    if st.button("Test Clock", type="primary", use_container_width=True, disabled=not bool(token_status), key="g5_clock_test"):
        try:
            refresh_clock_snapshot(store, week)
            store.trigger_clock_test(str(week["id"]), uuid4().hex, seconds=120)
            st.success("Clock test armed for two minutes. It uses clearly labeled sample content and does not touch Week data. On a non-Sunday test, allow up to about a minute for the clock to check in.")
        except Exception as exc:
            st.error(f"Clock test could not start: {exc}")

    with st.expander("One-time clock setup", expanded=False):
        st.caption("This is a separate headless Sunday script. Leave the existing school Class Schedule and Fact Challenge clock scripts unchanged.")
        script_path = Path(__file__).with_name("awtrix") / "PickemSunday.ax"
        if script_path.exists():
            st.download_button("Download PickemSunday.ax", script_path.read_text("utf-8"), file_name="PickemSunday.ax", mime="text/plain", use_container_width=True, key="g5_clock_script_download")

        label = "Rotate Clock Token" if token_status else "Generate Clock Token"
        if st.button(label, use_container_width=True, key="g5_clock_token_generate"):
            try:
                token, digest, hint = new_clock_token()
                store.replace_clock_token_hash(digest, hint)
                st.session_state["g5_clock_token_once"] = token
                st.rerun()
            except Exception as exc:
                st.error(f"Clock token could not be created: {exc}")

        one_time = st.session_state.pop("g5_clock_token_once", None)
        if one_time:
            st.warning("Copy this token into the AWTRIX script settings now. For security, the app stores only its SHA-256 hash and will not be able to show this plaintext token again.")
            st.code(str(one_time), language=None)

        st.markdown(
            "1. In AWTRIX, open **Scripts**, add/import `PickemSunday.ax`, and save it as its own script.  \n"
            f"2. In that script's settings, set **Supabase URL** to `{getattr(store, 'url', 'your Supabase URL')}`.  \n"
            "3. Paste your Supabase project's **publishable/anon key** — never the secret/service-role key.  \n"
            "4. Paste the scoped **Clock token** generated above.  \n"
            "5. Save/enable the script, then return here and press **Test Clock**."
        )
        st.caption("The Pick'em script only receives safe display text over a narrow read-only RPC. It is inactive outside the Sunday broadcast window except when Test Clock is armed.")


def _render_legacy_diagnostics(store, week: dict[str, Any]) -> None:
    players = store.get_registered_players()
    if players:
        with st.expander("Gate 2 lineup-builder demo", expanded=False):
            st.caption("Commissioner-only. Uses the isolated synthetic test week and never touches the real NFL week.")
            labels = [f"{row.get('emoji') or '👤'} {row.get('nickname') or 'Player'}" for row in players]
            by_label = {label: str(row["id"]) for label, row in zip(labels, players)}
            selected_label = st.selectbox("Demo as player", labels, key="g5_gate2_demo_player")
            if st.button("Preview Gate 2 Lineup Builder", use_container_width=True, key="g5_gate2_demo"):
                st.session_state.gate2_demo = True
                st.session_state.gate2_demo_player_id = by_label[selected_label]
                st.session_state.use_demo_week = True
                st.session_state.builder_mode = "home"
                st.session_state.builder_position = None
                st.session_state.pop("builder_return_mode", None)
                st.rerun()

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





def _render_diagnostics(store, week: dict[str, Any]) -> None:
    st.markdown("#### Diagnostics")
    st.caption("Recovery, launch checks, and old build tools live here so the everyday Commissioner tabs stay clean.")

    with st.expander("Launch readiness & full-week checks", expanded=False):
        render_launch_readiness(store, week)

    with st.expander("Database & recent activity", expanded=False):
        if st.button("Check Database Connection", use_container_width=True, key="g5_diag_db_check"):
            st.toast("Database connected." if store.healthcheck() else "Database check failed.")
        st.markdown("**Automation recovery**")
        if store.refresh_lease_available():
            st.success("Fallback lease armed. GitHub remains primary; active players can recover a late critical refresh.")
        else:
            st.warning("Fallback lease unavailable. GitHub scheduling still works, but db/005_automation_hardening.sql should be checked.")
        latest_recovery = store.latest_data_run("app_recovery", week_id=str(week["id"]))
        if latest_recovery:
            status = "PASS" if latest_recovery.get("success") is True else ("FAIL" if latest_recovery.get("success") is False else "RUNNING")
            action = str((latest_recovery.get("metadata") or {}).get("action") or "refresh")
            st.caption(f"Last app fallback: {action} • {status} • {_ago(latest_recovery.get('completed_at') or latest_recovery.get('started_at'))}")
        runs = store.get_recent_data_runs(week_id=str(week["id"]), limit=12)
        if runs:
            display = []
            for row in runs:
                display.append({
                    "When": _ago(row.get("completed_at") or row.get("started_at")),
                    "Run": str(row.get("run_type") or "").replace("_", " ").title(),
                    "Result": "PASS" if row.get("success") is True else ("FAIL" if row.get("success") is False else "RUNNING"),
                    "Message": row.get("message") or "",
                })
            st.dataframe(display, hide_index=True, use_container_width=True)
        else:
            st.caption("No recent run history for this week.")

    _render_live_dress_rehearsal(store, week)

    with st.expander("Legacy build diagnostics & demos", expanded=False):
        _render_legacy_diagnostics(store, week)
def render_commissioner_dashboard(store, *, pin_pepper: str) -> None:
    st.markdown("### Commissioner")
    st.caption("Manage the current Sunday, players, corrections, clock broadcast, and recovery tools.")
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

    commissioner_tools = ["Week", "Players", "Corrections", "Clock", "Diagnostics"]
    if st.session_state.get("g5_tool") not in commissioner_tools:
        st.session_state["g5_tool"] = "Week"
    tool = st.segmented_control(
        "Commissioner tool",
        commissioner_tools,
        default="Week",
        key="g5_tool",
        width="stretch",
        label_visibility="collapsed",
    ) or "Week"

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
    elif tool == "Clock":
        _render_clock(store, week)
    else:
        _render_diagnostics(store, week)
