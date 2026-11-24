"""Small mobile-friendly Thanksgiving surface; Sunday navigation remains unchanged."""
from __future__ import annotations

from datetime import datetime, timezone
from html import escape

import streamlit as st

from gate4 import build_weekly_leaderboard
from turkey_trophy_badge import trophy_badge_html, trophy_badge_markdown
from turkey_bowl import TurkeyBowlError, TurkeyBowlService, is_locked, is_open
from weekly import ET, POSITIONS, et_label, parse_timestamp

UTC = timezone.utc
TURKEY_BOWL_UI_SCHEMA_VERSION = 2  # Thanksgiving tile picker, no scoring or DB changes.


def _name(row: dict) -> str:
    status = str(row.get("availability_status") or "HEALTHY")
    suffix = f" ⚠️ {status.title()}" if status != "HEALTHY" else ""
    return f"{row['player_name']} ({row['team_abbr']}){suffix}"


def _error(exc: Exception) -> None:
    st.error(f"Turkey Bowl action could not be completed: {exc}")


def render_home_card(store, event: dict, player: dict) -> bool:
    """Return True when the holiday page has taken over the Sunday surface."""
    service = TurkeyBowlService(store)
    date = datetime.now(ET).date()
    event_date = datetime.fromisoformat(str(event["game_date"])).date()
    if st.session_state.get("turkey_bowl_open"):
        if st.button("← Back to Sunday Pick’em", use_container_width=True, key="turkey_back_sunday"):
            st.session_state.turkey_bowl_open = False
            st.rerun()
        render_turkey_bowl(service, event, player)
        return True
    # Only show a launch card around Thanksgiving, not throughout an entire season.
    if not (0 <= (event_date - date).days <= 21 or 0 <= (date - event_date).days <= 9):
        return False
    st.markdown("### 🦃 Teal’s Turkey Bowl")
    st.caption("Three Thanksgiving games • A separate starting five • Full season points • The turkey trophy")
    state = "Champion crowned" if event.get("finalized_at") else (
        "Live scores" if is_locked(event) else ("Picks open" if is_open(event) else "Coming Thanksgiving week"))
    st.markdown(f"**{state}** · Locks {et_label(event['locks_at'])}")
    if st.button("🦃 Open Turkey Bowl", type="primary", use_container_width=True, key="turkey_open_from_sunday"):
        st.session_state.turkey_bowl_open = True
        st.rerun()
    st.divider()
    return False


def _draft_key(event_id: str, player_id: str, position: str, field: str) -> str:
    """A separate draft for every Thanksgiving player/position; never reuse Sunday keys."""
    return f"turkey_draft::{event_id}::{player_id}::{position}::{field}"


def _stage_starter(event_id: str, player_id: str, position: str, row_id: str) -> None:
    st.session_state[_draft_key(event_id, player_id, position, "starter")] = row_id
    # A newly selected starter must never silently inherit another starter's backup.
    st.session_state.pop(_draft_key(event_id, player_id, position, "backup"), None)
    st.session_state[_draft_key(event_id, player_id, position, "step")] = "starter"


def _stage_backup(event_id: str, player_id: str, position: str, row_id: str) -> None:
    # Empty string explicitly means the user chose no backup, not "keep the old one".
    st.session_state[_draft_key(event_id, player_id, position, "backup")] = row_id


def _draft_selection(event_id: str, player_id: str, position: str,
                     saved: dict, candidates: dict[str, dict]) -> tuple[str, str]:
    """Resolve staged choices without writing or altering an existing saved pick."""
    saved_starter = str(saved.get("pool_player_id") or "")
    saved_backup = str(saved.get("emergency_pool_player_id") or "")
    staged_starter = st.session_state.get(_draft_key(event_id, player_id, position, "starter"))
    starter_id = str(staged_starter) if staged_starter is not None else saved_starter
    staged_backup = st.session_state.get(_draft_key(event_id, player_id, position, "backup"))
    if staged_backup is not None:
        backup_id = str(staged_backup)
    elif starter_id == saved_starter:
        backup_id = saved_backup
    else:
        backup_id = ""
    return starter_id, backup_id


def _clear_draft(event_id: str, player_id: str, position: str) -> None:
    for field in ("starter", "backup", "step"):
        st.session_state.pop(_draft_key(event_id, player_id, position, field), None)


def _move_to_position_on_next_render() -> None:
    """Update an existing segmented widget BEFORE it is instantiated on the next rerun."""
    nxt = st.session_state.pop("turkey_next_position", None)
    if nxt in POSITIONS:
        st.session_state["turkey_edit_position"] = nxt


def _turkey_player_tile(row: dict, *, selected: bool, key: str,
                        event_id: str, player_id: str, position: str, as_backup: bool) -> None:
    # Reuse Sunday's real full-width button component, including its selected
    # border, QUESTIONABLE badge, mobile tap target and team/kickoff metadata.
    # Never reuse Sunday's session keys or lineup save callbacks.
    from weekly_ui import _render_player_card_button

    stage = _stage_backup if as_backup else _stage_starter
    _render_player_card_button(
        row, key=key, selected=selected, on_click=stage,
        args=(event_id, player_id, position, str(row["id"])),
    )


def _lineup_picker(service: TurkeyBowlService, event: dict, player: dict) -> None:
    eid, pid = str(event["id"]), str(player["id"])
    rows = service.pool(eid, visible_only=True)
    if any(len([r for r in rows if r["position"] == p]) != 5 for p in POSITIONS):
        st.info("The Thanksgiving five-player choices are being prepared. Your Sunday lineup is unaffected.")
        return
    lineup, picks = service.lineup(eid, pid)
    own = {p["position"]: p for p in picks}
    all_rows = {str(p["id"]): p for p in service.pool(eid)}
    complete = len(own)
    st.markdown(f"**Your Thanksgiving five: {complete} of 5 saved**")
    if lineup and lineup.get("confirmed_at"):
        st.success("✅ Turkey Bowl lineup confirmed. You can still change it before Thursday's lock.")
    for position in POSITIONS:
        pick = own.get(position)
        if pick:
            starter = all_rows.get(str(pick.get("pool_player_id"))) or {}
            backup = all_rows.get(str(pick.get("emergency_pool_player_id"))) if pick.get("emergency_pool_player_id") else None
            backup_text = f" • Backup: {backup.get('player_name')}" if backup else ""
            st.caption(f"{position}: {starter.get('player_name', 'Unavailable')} ({starter.get('team_abbr','?')}){backup_text}")

    # Keep the final confirmation immediately after the five-player review,
    # not beneath another entire page of selectable cards on an iPhone.
    if complete == 5:
        pending_unsaved = any(
            _draft_selection(eid, pid, p, own.get(p) or {}, {}) != (
                str((own.get(p) or {}).get("pool_player_id") or ""),
                str((own.get(p) or {}).get("emergency_pool_player_id") or ""),
            )
            for p in POSITIONS
        )
        if pending_unsaved:
            st.caption("Save your changed position before confirming your Thanksgiving five.")
        if st.button("✅ Confirm my Turkey Bowl lineup", use_container_width=True,
                     disabled=pending_unsaved, key="turkey_confirm"):
            try:
                service.confirm(event, pid)
                st.success("Turkey Bowl lineup confirmed!")
                st.rerun()
            except Exception as exc:
                _error(exc)

    _move_to_position_on_next_render()
    position = st.segmented_control("Edit position", POSITIONS, default="QB", key="turkey_edit_position") or "QB"
    # Match Sunday: hold one stable, player-specific card order for each position.
    from weekly_ui import _stable_order
    display_rows = _stable_order(pid, eid, position, [p for p in rows if p["position"] == position])
    candidates = {str(p["id"]): p for p in display_rows
                  if p.get("availability_status") != "OUT"}
    current = own.get(position) or {}
    starter_id, backup_id = _draft_selection(eid, pid, position, current, candidates)
    step_key = _draft_key(eid, pid, position, "step")
    step = st.session_state.get(step_key, "starter")
    if step not in ("starter", "backup"):
        step = "starter"
    st.markdown(f"### Choose your {position}" if step == "starter" else f"### Emergency {position} backup")
    if starter_id and starter_id not in candidates:
        st.warning("Your saved starter is no longer selectable. Choose an available replacement before saving.")
    if backup_id and backup_id not in candidates:
        st.warning("Your previous backup is no longer selectable. Select another backup or clear it before saving.")

    if step == "starter":
        st.caption("Tap a player tile to highlight your starter. Nothing saves until you finish this position.")
        for row in display_rows:
            _turkey_player_tile(row, selected=str(row["id"]) == starter_id,
                key=f"turkey_starter::{eid}::{pid}::{position}::{row['id']}",
                event_id=eid, player_id=pid, position=position, as_backup=False)
        if st.button("Next: Emergency Backup →", type="primary", use_container_width=True,
                     disabled=starter_id not in candidates,
                     key=f"turkey_next_backup::{eid}::{pid}::{position}"):
            st.session_state[step_key] = "backup"
            st.rerun()
    else:
        selected_starter = candidates.get(starter_id)
        if selected_starter is None:
            st.session_state[step_key] = "starter"
            st.rerun()
        st.caption(f"Starter: {selected_starter['player_name']} ({selected_starter['team_abbr']})")
        st.info("A saved emergency backup plays only if your starter is officially OUT. "
                "You can leave it empty unless your starter is QUESTIONABLE.")
        for row in display_rows:
            if str(row["id"]) == starter_id:
                continue
            _turkey_player_tile(row, selected=str(row["id"]) == backup_id,
                key=f"turkey_backup::{eid}::{pid}::{position}::{row['id']}",
                event_id=eid, player_id=pid, position=position, as_backup=True)
        if st.button("No emergency backup" + (" ✓" if not backup_id else ""),
                     use_container_width=True, key=f"turkey_clear_backup::{eid}::{pid}::{position}"):
            _stage_backup(eid, pid, position, "")
            st.rerun()
        if str(selected_starter.get("availability_status") or "HEALTHY") == "QUESTIONABLE" and not backup_id:
            st.warning("Your starter is QUESTIONABLE. Choose a healthy backup before confirming your lineup.")

        left, right = st.columns([1, 2])
        with left:
            if st.button("← Change starter", use_container_width=True,
                         key=f"turkey_back_starter::{eid}::{pid}::{position}"):
                st.session_state[step_key] = "starter"
                st.rerun()
        with right:
            following = POSITIONS[POSITIONS.index(position) + 1] if position != POSITIONS[-1] else None
            label = f"Save {position} · Next: {following} →" if following else "Save K · Review my five →"
            if st.button(label, type="primary", use_container_width=True,
                         disabled=bool(backup_id and (backup_id not in candidates or backup_id == starter_id)),
                         key=f"turkey_save_next::{eid}::{pid}::{position}"):
                try:
                    changed = (
                        starter_id != str(current.get("pool_player_id") or "")
                        or backup_id != str(current.get("emergency_pool_player_id") or "")
                    )
                    if changed:
                        service.save_pick(event, pid, position, starter_id, backup_id or None)
                    _clear_draft(eid, pid, position)
                    if following:
                        st.session_state["turkey_next_position"] = following
                    if changed:
                        st.toast(f"{position} saved for Turkey Bowl.")
                    st.rerun()
                except Exception as exc:
                    _error(exc)


def _locked_view(service: TurkeyBowlService, event: dict, player: dict) -> None:
    eid = str(event["id"])
    lineup, picks = service.lineup(eid, str(player["id"]))
    pool = {str(p["id"]): p for p in service.pool(eid)}
    st.markdown("### 🔒 Thanksgiving lineups locked")
    if picks:
        for p in sorted(picks, key=lambda p: POSITIONS.index(p["position"])):
            starter = pool.get(str(p["pool_player_id"])) or {}
            backup = pool.get(str(p.get("emergency_pool_player_id"))) if p.get("emergency_pool_player_id") else None
            name = starter.get("player_name") or "Unknown"
            suffix = f" (backup: {backup.get('player_name')})" if backup else ""
            st.markdown(f"**{escape(p['position'])}:** {escape(name)}{escape(suffix)}")
    else:
        st.caption("No Thanksgiving selections were saved for this event.")
    if not lineup or len(picks) < 5:
        st.caption("Missing positions score zero, as in Sunday Pick’em.")
    if not event.get("refreshed_at"):
        st.caption("Live scores begin with Thursday's games. Refreshing your screen does not alter your lineup.")
    else:
        st.caption(f"Last Thanksgiving scoring update: {et_label(event['refreshed_at'])}")
    _live_scores(service, event, str(player["id"]))


@st.fragment(run_every="30s")
def _live_scores(service: TurkeyBowlService, event: dict, current_player_id: str) -> None:
    try:
        # Re-read event status on each display refresh; score retrieval is only
        # done in the dedicated worker, never by a phone.
        event = service.event(int(event["season"])) or event
        leaderboard = service.leaderboard(event)
        games = service.games(str(event["id"]))
    except Exception as exc:
        _error(exc)
        return
    st.markdown("### 🏆 Turkey Bowl Standings")
    if not leaderboard:
        st.caption("Nobody submitted a lineup for this year's Turkey Bowl.")
        return
    if event.get("finalized_at"):
        winners = [r for r in leaderboard if r["rank"] == 1]
        st.success(trophy_badge_markdown() + " Turkey Bowl Champion: " + ", ".join(r["nickname"] for r in winners))
    elif any(g.get("game_status") in {"LIVE", "FINAL"} for g in games):
        st.caption("Live and provisional until scores are finalized Friday. Equal scores share their rank.")
    else:
        st.caption("Lineups revealed. Kickoff scores begin at 1:00 PM ET.")
    for g in games:
        home, away = escape(str(g["home_team"])), escape(str(g["away_team"]))
        status = str(g.get("game_status") or "SCHEDULED")
        score = f" · {g.get('away_score', '-')}-{g.get('home_score', '-')}" if status != "SCHEDULED" else ""
        st.caption(f"{away} @ {home} · {status}{score}")
    for r in leaderboard:
        you = " · YOU" if str(r["player_id"]) == current_player_id else ""
        trophy = trophy_badge_html() if event.get("finalized_at") and int(r["rank"]) == 1 else ""
        st.markdown(
            f"<strong>{r['rank']}. {escape(str(r['emoji']))} {escape(str(r['nickname']))}{trophy}{escape(you)}</strong> — {r['score']:.1f} pts",
            unsafe_allow_html=True,
        )
        with st.expander(f"{r['nickname']} starting five", expanded=False):
            for item in r["roster"]:
                p = item.get("player") or {}
                name = escape(str(p.get("player_name") or "—"))
                note = " · backup activated" if item.get("emergency_activated") else ""
                st.caption(f"{item['position']} · {name} · {item['points']:.1f}{note}")


def render_turkey_bowl(service: TurkeyBowlService, event: dict, player: dict) -> None:
    st.title("🦃 Teal’s Turkey Bowl")
    st.caption("Thanksgiving Day • Three games • Five starters • One Turkey Bowl champion")
    st.markdown("**Bears @ Lions · Eagles @ Cowboys · Chiefs @ Bills**" if int(event["season"]) == 2026 else "Thanksgiving NFL tripleheader")
    st.caption(f"All five picks lock {et_label(event['locks_at'])} · Full regular season points are awarded to the final rankings.")
    if not event.get("published_at"):
        if is_locked(event):
            st.warning("Turkey Bowl's pool was not published before lock. The commissioner must investigate; the app will not invent selections or awards.")
        else:
            st.info(f"Turkey Bowl opens {et_label(event['opens_at'])}. Selections will appear when its player pool is published.")
    elif is_locked(event):
        _locked_view(service, event, player)
    elif is_open(event):
        _lineup_picker(service, event, player)
    else:
        st.info(f"Selections open {et_label(event['opens_at'])}.")


def render_commissioner_turkey(store) -> None:
    """Shown only inside the existing authenticated Commissioner dashboard."""
    service = TurkeyBowlService(store)
    try:
        event = service.event(2026)
    except Exception as exc:
        st.error(f"Turkey Bowl database setup is unavailable: {exc}")
        return
    if not event:
        st.caption("No 2026 Turkey Bowl event configured.")
        return
    st.markdown("#### 🦃 Turkey Bowl Controls")
    st.caption(f"Holiday pool: {'published' if event.get('published_at') else 'not published'} · "
               f"Awards: {'finalized' if event.get('finalized_at') else 'pending'} · "
               f"Lock: {et_label(event['locks_at'])}")
    a, b = st.columns(2)
    with a:
        if st.button("Publish Holiday Pool", disabled=bool(event.get('published_at')) or datetime.now(UTC) < parse_timestamp(event['opens_at']),
                     use_container_width=True, key="turkey_admin_publish"):
            try:
                result = service.publish(event)
                st.success(f"Turkey Bowl pool prepared: {result}")
                st.rerun()
            except Exception as exc:
                _error(exc)
    with b:
        if st.button("Refresh Turkey Data", disabled=not event.get('published_at') or bool(event.get('finalized_at')),
                     use_container_width=True, key="turkey_admin_refresh"):
            try:
                if is_locked(event):
                    st.write(service.refresh_scores(event))
                st.write({"injuries_updated": service.refresh_injuries(event)})
                st.rerun()
            except Exception as exc:
                _error(exc)
    if event.get("published_at"):
        lineups = list(service.table("special_lineups").select("id,confirmed_at,player_id").eq("event_id", str(event["id"])).execute().data or [])
        st.caption(f"{len(lineups)} submitted lineups · {sum(bool(r.get('confirmed_at')) for r in lineups)} confirmed")
        with st.expander("Player pool adjustments / score corrections"):
            pool = service.pool(str(event["id"]))
            by_id = {str(r["id"]): r for r in pool}
            if not is_locked(event):
                # Reserve promotion preserves all saved starters and backups;
                # impacted players must choose a replacement before lock.
                position = st.selectbox("Position", POSITIONS, key="turkey_admin_pos")
                visible = [p for p in pool if p["position"] == position and p["is_visible"]]
                hidden = [p for p in pool if p["position"] == position and not p["is_visible"] and p["availability_status"] != "OUT"]
                outgoing = st.selectbox("Visible player to replace", [str(p["id"]) for p in visible],
                                       format_func=lambda pid: _name(by_id[pid]), key="turkey_out")
                incoming = st.selectbox("Reserve to promote", [str(p["id"]) for p in hidden],
                                       format_func=lambda pid: _name(by_id[pid]), key="turkey_in")
                if st.button("Promote Reserve", disabled=not incoming or not outgoing, key="turkey_admin_promote"):
                    try:
                        service.promote_reserve(event, outgoing, incoming)
                        st.success("Reserve promoted. Existing locked-in selections have not been erased.")
                        st.rerun()
                    except Exception as exc:
                        _error(exc)
            else:
                target = st.selectbox("Correct Thanksgiving player", [str(p["id"]) for p in pool],
                    format_func=lambda pid: _name(by_id[pid]), key="turkey_correct_target")
                current = by_id[target].get("manual_score_override") if target else None
                score = st.number_input("Corrected fantasy points", min_value=-100.0, max_value=250.0,
                                        value=float(current if current is not None else by_id[target].get("score_total") or 0),
                                        step=.1, key="turkey_correct_score") if target else None
                reason = st.text_input("Reason for correction", key="turkey_correct_reason")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Set Score", disabled=not target or len(reason.strip()) < 3, use_container_width=True):
                        try:
                            service.correct_score(event, target, score, reason)
                            st.success("Thanksgiving score corrected.")
                            st.rerun()
                        except Exception as exc:
                            _error(exc)
                with col2:
                    if st.button("Clear Override", disabled=not target or current is None or len(reason.strip()) < 3, use_container_width=True):
                        try:
                            service.correct_score(event, target, None, reason)
                            st.success("Original provider score restored.")
                            st.rerun()
                        except Exception as exc:
                            _error(exc)
    if is_locked(event):
        if st.button("Finalize Turkey Bowl Awards", disabled=bool(event.get("finalized_at")), use_container_width=True, key="turkey_admin_finalize"):
            try:
                st.success(f"Thanksgiving results archived: {service.archive(event)}")
                st.rerun()
            except Exception as exc:
                _error(exc)
