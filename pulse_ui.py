"""One small Sunday Pulse card + opt-in, collapsed reactions.

Designed to slot into existing Sunday surfaces, not create navigation or feeds.
Server-side Supabase app_meta stores check-ins and one emoji choice per user/week.
"""
from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from typing import Any

import streamlit as st

from weekly import week_phase

from pickem_pulse import (
    REACTION_OPTIONS, live_pulse, personal_goal, pregame_pulse,
    previous_results, reaction_totals, snapshot_for,
)


def _pulse_card(pulse: dict[str, str]) -> None:
    # Use the app's existing compact card: no new CSS, menu, or navigation item.
    st.markdown(
        '<div class="card-tight">'
        '<div class="eyebrow">🏈 YOUR PICK’EM PULSE</div>'
        f'<strong>{escape(pulse["heading"])}</strong>'
        f'<div class="small">{escape(pulse["detail"])}</div>'
        f'<div class="small">{escape(pulse["goal"] if pulse["goal"].startswith(("🎯", "✅")) else "🎯 " + pulse["goal"])}</div>'
        '</div>', unsafe_allow_html=True,
    )


def render_pregame_pulse(store: Any, week: dict[str, Any], player: dict[str, Any]) -> None:
    if week.get("is_demo"):
        return
    try:
        history = store.get_weekly_results(season=int(week.get("season") or 2026))
        pulse = pregame_pulse(history, str(player["id"]), int(week.get("nfl_week") or 0))
        _pulse_card(pulse)
    except Exception:
        # The real lineup builder should never fail because the optional Pulse fails.
        return


def _last_checkin(store: Any, week_id: str, player_id: str,
                  leaderboard: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Read once/session; update a saved check-in at most once per 5 minutes.

    We keep the initial comparison stable while a screen auto-refreshes; the
    saved check-in can be read next time, including from another device.
    """
    current = snapshot_for(leaderboard, player_id)
    if not current:
        return None
    key = f"pickem_pulse_checkin:{week_id}:{player_id}"
    session_key = f"pulse_initial:{week_id}:{player_id}"
    save_key = f"pulse_last_saved:{week_id}:{player_id}"
    now = datetime.now(timezone.utc).timestamp()
    if session_key not in st.session_state:
        old = None
        try:
            value = (store.get_app_meta(key) or {}).get("value") or {}
            if isinstance(value, dict) and value.get("rank") is not None:
                old = value
        except Exception:
            pass
        st.session_state[session_key] = old
        st.session_state[save_key] = 0.0
    saved_key = f"pulse_last_snapshot:{week_id}:{player_id}"
    if now - float(st.session_state.get(save_key) or 0) >= 300:
        try:
            if st.session_state.get(saved_key) != current:
                store.set_app_meta(key, current)
                st.session_state[saved_key] = current
            st.session_state[save_key] = now
        except Exception:
            pass
    return st.session_state.get(session_key)


def render_live_pulse(store: Any, week: dict[str, Any], player: dict[str, Any],
                      leaderboard: list[dict[str, Any]], *, final: bool = False) -> None:
    if week.get("is_demo"):
        return
    player_id = str(player.get("id") or "")
    if not player_id:
        return
    try:
        rows = store.get_weekly_results(season=int(week.get("season") or 2026))
        history = previous_results(rows, int(week.get("nfl_week") or 0))
        goal = personal_goal(history, player_id)
        old = None if final else _last_checkin(store, str(week["id"]), player_id, leaderboard)
        pulse = live_pulse(leaderboard, player_id, old, goal, final=final)
        if pulse:
            _pulse_card(pulse)
    except Exception:
        return


def render_reactions(store: Any, week: dict[str, Any], player: dict[str, Any],
                     leaderboard: list[dict[str, Any]]) -> None:
    """One optional, collapsed cheer per player/week; only after lock."""
    sender = str(player.get("id") or "")
    eligible = {str(row.get("player_id")) for row in leaderboard if row.get("player_id")}
    others = [row for row in leaderboard if str(row.get("player_id")) != sender
              and row.get("player_id")]
    if week.get("is_demo") or week_phase(week) != "locked" or sender not in eligible or not others:
        return
    with st.expander("👏 Cheer someone on", expanded=False):
        st.caption("One friendly reaction per week. Change or remove it anytime.")
        try:
            rows = store.get_pulse_reactions(str(week["id"]))
        except Exception:
            st.caption("Reactions are temporarily unavailable.")
            return
        key = f"pickem_pulse_reaction:{week['id']}:{sender}"
        own = next(((r.get("value") or {}) for r in rows if str(r.get("key")) == key), {})
        selected = str(own.get("target") or "")
        valid = {str(r.get("player_id")) for r in others}
        if selected not in valid:
            selected = str(others[0]["player_id"])
        recipient = st.selectbox(
            "Cheer for", options=[str(r["player_id"]) for r in others],
            index=next((i for i, r in enumerate(others) if str(r["player_id"]) == selected), 0),
            format_func=lambda pid: next((f'{r.get("emoji") or "🏈"} {r.get("nickname") or "Player"}'
                                          for r in others if str(r["player_id"]) == pid), "Player"),
            key=f"pulse_recipient:{week['id']}:{sender}",
        )
        counts = reaction_totals(rows, recipient, eligible)
        columns = st.columns(4)
        for column, emoji in zip(columns, REACTION_OPTIONS):
            active = str(own.get("target") or "") == recipient and own.get("emoji") == emoji
            with column:
                if st.button(f"{emoji} {counts.get(emoji, 0)}", key=f"pulse_emoji:{week['id']}:{sender}:{emoji}",
                             help="Tap again to remove" if active else "React",
                             use_container_width=True, type="primary" if active else "secondary"):
                    try:
                        store.save_pulse_reaction(str(week["id"]), sender, recipient, "" if active else emoji)
                        st.rerun()
                    except Exception:
                        st.error("Couldn't save that reaction. Please try again.")
