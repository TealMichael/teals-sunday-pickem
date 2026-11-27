"""Small mobile-friendly Thanksgiving surface; Sunday navigation remains unchanged."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from html import escape

import streamlit as st

from gate4 import build_weekly_leaderboard
from turkey_trophy_badge import trophy_badge_html, trophy_badge_markdown
from turkey_loser_badge import loser_badge_html
from turkey_bowl import TurkeyBowlError, TurkeyBowlService, is_locked, is_open
from weekly import ET, POSITIONS, et_label, parse_timestamp

UTC = timezone.utc
TURKEY_BOWL_UI_SCHEMA_VERSION = 7  # Retain Turkey Bowl link below Sunday after Nov 29.


def _name(row: dict) -> str:
    status = str(row.get("availability_status") or "HEALTHY")
    suffix = f" ⚠️ {status.title()}" if status != "HEALTHY" else ""
    return f"{row['player_name']} ({row['team_abbr']}){suffix}"


def _error(exc: Exception) -> None:
    st.error(f"Turkey Bowl action could not be completed: {exc}")


def home_card_moves_below_sunday(event: dict, *, today: date | None = None) -> bool:
    """Feature Thanksgiving through Sunday; archive below Sunday from Monday.

    For Thanksgiving 2026 this moves the link Monday, November 30, ET.
    It does not delete the event, alter scoring, or affect Sunday lineups.
    """
    event_date = datetime.fromisoformat(str(event["game_date"])).date()
    return (today if today is not None else datetime.now(ET).date()) > event_date + timedelta(days=3)


def render_home_card(store, event: dict, player: dict) -> bool:
    """Return True when the holiday page has taken over the Sunday surface."""
    service = TurkeyBowlService(store)
    date = datetime.now(ET).date()
    event_date = datetime.fromisoformat(str(event["game_date"])).date()
    if st.session_state.get("turkey_bowl_open"):
        if st.button("← Back to Sunday Pick’em", use_container_width=True, key="turkey_back_sunday"):
            st.session_state["turkey_bowl_open"] = False
            st.session_state.pop(_view_key(str(event["id"]), str(player["id"])), None)
            for pos in POSITIONS:
                _clear_draft(str(event["id"]), str(player["id"]), pos)
            st.rerun()
        render_turkey_bowl(service, event, player)
        return True
    # Launch no earlier than three weeks out. Keep completed 2026 results
    # reachable below Sunday for the remainder of the 2026 app season.
    if date < event_date - timedelta(days=21):
        return False
    st.markdown("### 🦃 Teal’s Turkey Bowl")
    st.caption("Three Thanksgiving games • A separate starting five • Full season points • The turkey trophy")
    state = "Champion crowned" if event.get("finalized_at") else (
        "Live scores" if is_locked(event) else ("Picks open" if is_open(event) else "Coming Thanksgiving week"))
    st.markdown(f"**{state}** · Locks {et_label(event['locks_at'])}")
    # The existing Thursday lock controls both the destination and the label.
    # Before lock this opens the picker; after lock it opens live standings.
    # Finished events should no longer advertise scores as live.
    button_label = (
        "🏆 View final Turkey Bowl standings" if event.get("finalized_at") else
        "🦃 Click here for Live Turkey Day standings!" if is_locked(event) else
        "🦃 Open Turkey Bowl"
    )
    if st.button(button_label, type="primary", use_container_width=True, key="turkey_open_from_sunday"):
        st.session_state.turkey_bowl_open = True
        st.rerun()
    st.divider()
    return False


def _draft_key(event_id: str, player_id: str, position: str, field: str) -> str:
    """A separate draft for every Thanksgiving player/position; never reuse Sunday keys."""
    return f"turkey_draft::{event_id}::{player_id}::{position}::{field}"


def _stage_starter(event_id: str, player_id: str, position: str, row_id: str) -> None:
    # Stage only: no database write until Save is pressed. Sunday keys are never used.
    st.session_state[_draft_key(event_id, player_id, position, "starter")] = row_id
    # Discard stale draft state from the former Thanksgiving backup wizard.
    for obsolete in ("backup", "step"):
        st.session_state.pop(_draft_key(event_id, player_id, position, obsolete), None)


def _draft_selection(event_id: str, player_id: str, position: str, saved: dict) -> str:
    """Resolve the one Thanksgiving starter, ignoring any legacy saved backup."""
    staged = st.session_state.get(_draft_key(event_id, player_id, position, "starter"))
    return str(staged) if staged is not None else str(saved.get("pool_player_id") or "")


def _clear_draft(event_id: str, player_id: str, position: str) -> None:
    for field in ("starter", "backup", "step"):
        st.session_state.pop(_draft_key(event_id, player_id, position, field), None)


def _move_to_position_on_next_render() -> None:
    """Update an existing segmented widget BEFORE it is instantiated on the next rerun."""
    nxt = st.session_state.pop("turkey_next_position", None)
    if nxt in POSITIONS:
        st.session_state["turkey_edit_position"] = nxt


def _turkey_player_tile(row: dict, *, selected: bool, key: str,
                        event_id: str, player_id: str, position: str) -> None:
    # Use Sunday's visual card without reusing its selection state or save callbacks.
    from weekly_ui import _render_player_card_button

    _render_player_card_button(
        row, key=key, selected=selected, on_click=_stage_starter,
        args=(event_id, player_id, position, str(row["id"])),
    )


def _view_key(event_id: str, player_id: str) -> str:
    # Scope navigation to the holiday event and player; never reuse Sunday state.
    return f"turkey_view::{event_id}::{player_id}"


def _current_view(event_id: str, player_id: str, *, complete: bool, confirmed: bool) -> str:
    requested = st.session_state.get(_view_key(event_id, player_id))
    if not complete:
        return "edit"
    if confirmed:
        # A confirmed lineup is the landing screen unless the player chose Edit.
        return "edit" if requested == "edit" else "confirmed"
    # A changed starter invalidates confirmation in the existing database service.
    return "edit" if requested == "edit" else "review"


def _set_view(event_id: str, player_id: str, view: str) -> None:
    st.session_state[_view_key(event_id, player_id)] = view


def _lineup_summary(own: dict, all_rows: dict) -> None:
    # One compact markup block instead of five Streamlit caption blocks, which
    # otherwise create substantial whitespace on iPhone.
    entries = []
    for position in POSITIONS:
        pick = own.get(position) or {}
        starter = all_rows.get(str(pick.get("pool_player_id") or "")) or {}
        name = str(starter.get("player_name") or "Not selected")
        team = str(starter.get("team_abbr") or "")
        label = escape(name + (f" ({team})" if team else ""))
        entries.append(
            '<div class="tb-summary-row">'
            f'<span class="tb-summary-pos">{escape(position)}</span>'
            f'<span class="tb-summary-name">{label}</span>'
            '</div>'
        )
    st.markdown('<div class="tb-summary">' + ''.join(entries) + '</div>',
                unsafe_allow_html=True)


def _lineup_picker(service: TurkeyBowlService, event: dict, player: dict) -> None:
    eid, pid = str(event["id"]), str(player["id"])
    rows = service.pool(eid, visible_only=True)
    if any(len([r for r in rows if r["position"] == p]) != 5 for p in POSITIONS):
        st.info("The Thanksgiving five-player choices are being prepared. Your Sunday lineup is unaffected.")
        return
    lineup, picks = service.lineup(eid, pid)
    own = {p["position"]: p for p in picks}
    all_rows = {str(p["id"]): p for p in service.pool(eid)}
    complete = all(pos in own for pos in POSITIONS)
    confirmed = bool(lineup and lineup.get("confirmed_at"))
    view = _current_view(eid, pid, complete=complete, confirmed=confirmed)

    if view == "confirmed":
        st.success("✅ You're in the Turkey Bowl! Your five starters are confirmed.")
        st.markdown("#### Your Thanksgiving five")
        _lineup_summary(own, all_rows)
        st.caption("Your lineup locks Thursday, Nov 26 at 1:00 PM ET. You can edit it before then, but changed picks must be reconfirmed.")
        if st.button("Edit my picks", use_container_width=True,
                     key=f"turkey_edit_confirmed::{eid}::{pid}"):
            _set_view(eid, pid, "edit")
            st.rerun()
        return

    if view == "review":
        st.markdown("### Review your Thanksgiving five")
        st.caption("Check your five starters before entering the Turkey Bowl. No injury substitutions.")
        _lineup_summary(own, all_rows)
        # An unsaved staged change should never be silently included in the
        # confirmed lineup. Players must use Save first.
        pending_unsaved = any(
            _draft_selection(eid, pid, pos, own.get(pos) or {}) !=
            str((own.get(pos) or {}).get("pool_player_id") or "")
            for pos in POSITIONS
        )
        if pending_unsaved:
            st.warning("You have an unsaved player change. Edit and save it before confirming.")
        if st.button("✅ Confirm my Turkey Bowl lineup", type="primary", use_container_width=True,
                     disabled=pending_unsaved, key=f"turkey_confirm::{eid}::{pid}"):
            try:
                service.confirm(event, pid)
                # Read back the authoritative database state rather than assuming
                # a successful write; never show a false success banner.
                checked_lineup, checked_picks = service.lineup(eid, pid)
                if not checked_lineup or not checked_lineup.get("confirmed_at") or \
                        {p.get("position") for p in checked_picks} != set(POSITIONS):
                    raise TurkeyBowlError("Confirmation could not be verified. Please try again.")
                _set_view(eid, pid, "confirmed")
                st.rerun()
            except Exception as exc:
                _error(exc)
        if st.button("Edit a pick", use_container_width=True,
                     key=f"turkey_edit_review::{eid}::{pid}"):
            _set_view(eid, pid, "edit")
            st.rerun()
        return

    # Only the edit screen renders the player tiles. Confirmation/review screens
    # stay short and clear on a phone.
    st.markdown(f"**Your Thanksgiving five: {len(own)} of 5 saved**")
    if confirmed:
        st.caption("Your five are confirmed. Saving a different starter will require reconfirmation.")
    else:
        st.caption("Starter-only Turkey Bowl · no emergency backups · locks Thursday at 1 PM ET")
    _move_to_position_on_next_render()
    position = st.segmented_control("Edit position", POSITIONS, default="QB", key="turkey_edit_position") or "QB"
    from weekly_ui import _stable_order
    display_rows = _stable_order(pid, eid, position, [p for p in rows if p["position"] == position])
    candidates = {str(p["id"]): p for p in display_rows if p.get("availability_status") != "OUT"}
    current = own.get(position) or {}
    starter_id = _draft_selection(eid, pid, position, current)
    st.markdown(f"### Choose your {position}")
    if starter_id and starter_id not in candidates:
        st.warning("Your saved starter is OUT or unavailable. Choose an available replacement before saving.")
    elif starter_id and str(candidates[starter_id].get("availability_status") or "HEALTHY") == "QUESTIONABLE":
        st.warning("Your starter is QUESTIONABLE. There are no injury substitutions in Turkey Bowl.")
    st.caption("Tap a tile to highlight your starter; tap Save to keep the selection.")
    for row in display_rows:
        _turkey_player_tile(row, selected=str(row["id"]) == starter_id,
            key=f"turkey_starter::{eid}::{pid}::{position}::{row['id']}",
            event_id=eid, player_id=pid, position=position)

    remaining = [p for p in POSITIONS if p not in set(own) | {position}]
    next_is_review = not remaining
    following = (next((p for p in remaining if POSITIONS.index(p) > POSITIONS.index(position)),
                      remaining[0]) if remaining else None)
    label = (f"Save {position} · Review my five →" if next_is_review else
             f"Save {position} · Next: {following} →")
    if st.button(label, type="primary", use_container_width=True,
                 disabled=starter_id not in candidates,
                 key=f"turkey_save_next::{eid}::{pid}::{position}"):
        try:
            changed = starter_id != str(current.get("pool_player_id") or "")
            if changed:
                service.save_pick(event, pid, position, starter_id)
            _clear_draft(eid, pid, position)
            if next_is_review:
                _set_view(eid, pid, "review")
            elif following:
                st.session_state["turkey_next_position"] = following
            # No rerun-time toast: it disappears before mobile users can see it.
            st.rerun()
        except Exception as exc:
            _error(exc)
    if complete:
        # Allows leaving the editor without touching the saved starter.
        if st.button("Back to my lineup", use_container_width=True,
                     key=f"turkey_return_summary::{eid}::{pid}"):
            # Discard staged edits that were never saved; never create a false
            # mismatch between the review screen and the database.
            for pos in POSITIONS:
                _clear_draft(eid, pid, pos)
            _set_view(eid, pid, "confirmed" if confirmed else "review")
            st.rerun()


def _locked_view(service: TurkeyBowlService, event: dict, player: dict) -> None:
    # Render the live leaderboard first, before the secondary lineup queries.
    # Existing 30-second fragment updates and scoring remain unchanged.
    _live_scores(service, event, str(player["id"]))
    eid = str(event["id"])
    lineup, picks = service.lineup(eid, str(player["id"]))
    pool = {str(p["id"]): p for p in service.pool(eid)}
    st.markdown("### 🔒 Your locked Thanksgiving five")
    if picks:
        for p in sorted(picks, key=lambda p: POSITIONS.index(p["position"])):
            starter = pool.get(str(p["pool_player_id"])) or {}
            name = starter.get("player_name") or "Unknown"
            st.markdown(f"**{escape(p['position'])}:** {escape(name)}")
    else:
        st.caption("No Thanksgiving selections were saved for this event.")
    if not lineup or len(picks) < 5:
        st.caption("Missing positions score zero, as in Sunday Pick’em.")
    if not event.get("refreshed_at"):
        st.caption("Live scores begin with Thursday's games. Refreshing your screen does not alter your lineup.")
    else:
        st.caption(f"Last Thanksgiving scoring update: {et_label(event['refreshed_at'])}")


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
    loser_ids = service.loser_badge_ids(int(event["season"])) if event.get("finalized_at") else set()
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
        loser = loser_badge_html() if str(r.get("player_id") or "") in loser_ids else ""
        st.markdown(
            f"<strong>{r['rank']}. {escape(str(r['emoji']))} {escape(str(r['nickname']))}{trophy}{escape(you)}</strong> — {r['score']:.1f} pts",
            unsafe_allow_html=True,
        )
        with st.expander(f"{r['nickname']} starting five", expanded=False):
            for item in r["roster"]:
                p = item.get("player") or {}
                name = escape(str(p.get("player_name") or "—"))
                st.caption(f"{item['position']} · {name} · {item['points']:.1f}")


def _turkey_mobile_styles() -> None:
    # Scoped classes: no global Sunday styling or shared bottom-navigation changes.
    st.markdown("""<style>
    .tb-title {font-size:clamp(1.8rem, 5vw, 2.7rem); font-weight:800;
      letter-spacing:-.035em; line-height:1.18; margin:1.1rem 0 .75rem;}
    .tb-summary {background:var(--secondary-background-color, #fff);
      border:1px solid rgba(120,140,150,.27); border-radius:14px;
      padding:.45rem .9rem; margin:.65rem 0 1rem;}
    .tb-summary-row {display:flex; align-items:center; gap:.65rem;
      padding:.38rem 0; min-height:2rem;}
    .tb-summary-row + .tb-summary-row {border-top:1px solid rgba(120,140,150,.13);}
    .tb-summary-pos {flex:0 0 2.3rem; text-align:center; font-size:.8rem;
      font-weight:750; color:#0f766e; background:#e8f5f2;
      border-radius:9px; padding:.19rem .15rem;}
    .tb-summary-name {font-weight:600; font-size:.97rem; overflow-wrap:anywhere;}
    .tb-bottom-clearance {height:calc(8rem + env(safe-area-inset-bottom, 0px));}
    @media (max-width:540px) {.tb-title {font-size:1.72rem; margin:.8rem 0 .65rem;}}
    </style>""", unsafe_allow_html=True)


def render_turkey_bowl(service: TurkeyBowlService, event: dict, player: dict) -> None:
    _turkey_mobile_styles()
    st.markdown('<h1 class="tb-title">🦃 Teal’s Turkey Bowl</h1>', unsafe_allow_html=True)
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
    # Clearance so the final Turkey Bowl control can scroll above the fixed
    # bottom nav on iPhone; shared Sunday navigation remains untouched.
    st.markdown('<div class="tb-bottom-clearance"></div>', unsafe_allow_html=True)


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
                # Reserve promotion preserves existing saved starters;
                # affected players may need to select a replacement before lock.
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
