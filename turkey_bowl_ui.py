"""Small mobile-friendly Thanksgiving surface; Sunday navigation remains unchanged."""
from __future__ import annotations

from datetime import datetime, timezone
from html import escape

import streamlit as st

from gate4 import build_weekly_leaderboard
from turkey_bowl import TurkeyBowlError, TurkeyBowlService, is_locked, is_open
from weekly import ET, POSITIONS, et_label, parse_timestamp

UTC = timezone.utc


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


def _lineup_picker(service: TurkeyBowlService, event: dict, player: dict) -> None:
    eid = str(event["id"])
    rows = service.pool(eid, visible_only=True)
    if any(len([r for r in rows if r["position"] == p]) != 5 for p in POSITIONS):
        st.info("The Thanksgiving five-player choices are being prepared. Your Sunday lineup is unaffected.")
        return
    lineup, picks = service.lineup(eid, str(player["id"]))
    own = {p["position"]: p for p in picks}
    all_rows = {str(p["id"]): p for p in service.pool(eid)}
    complete = len(own)
    st.markdown(f"**Your Thanksgiving five: {complete} of 5 saved**")
    if lineup and lineup.get("confirmed_at"):
        st.success("✅ Turkey Bowl lineup confirmed. You can still change it before Thursday's lock.")
    for pos in POSITIONS:
        pick = own.get(pos)
        if pick:
            starter = all_rows.get(str(pick.get("pool_player_id"))) or {}
            backup = all_rows.get(str(pick.get("emergency_pool_player_id"))) if pick.get("emergency_pool_player_id") else None
            backup_text = f" • Backup: {backup.get('player_name')}" if backup else ""
            st.caption(f"{pos}: {starter.get('player_name', 'Unavailable')} ({starter.get('team_abbr','?')}){backup_text}")

    pos = st.segmented_control("Edit position", POSITIONS, default="QB", key="turkey_edit_position")
    pos = pos or "QB"
    candidates = [p for p in rows if p["position"] == pos and p["availability_status"] != "OUT"]
    by_id = {str(p["id"]): p for p in candidates}
    current = own.get(pos) or {}
    starter_id = str(current.get("pool_player_id") or "")
    backup_id = str(current.get("emergency_pool_player_id") or "")
    if starter_id and starter_id not in by_id:
        st.warning("Your saved starter is no longer a selectable option. Please choose a replacement.")
    st.markdown(f"#### {pos} — Thanksgiving picks")
    with st.form(f"turkey_position_form_{eid}_{pos}"):
        starter = st.selectbox("Starter", options=[None, *by_id],
              index=([None, *by_id].index(starter_id) if starter_id in by_id else 0),
              format_func=lambda v: "Select a starter" if v is None else _name(by_id[v]),
              key=f"turkey_starter_{eid}_{pos}")
        # Keep options stable inside a Streamlit form; the chosen starter is
        # validated on submit instead of dynamically changing backup choices.
        backup_options = [None, *by_id]
        backup = st.selectbox("Emergency backup (recommended for every position)", options=backup_options,
              index=(backup_options.index(backup_id) if backup_id in backup_options else 0),
              format_func=lambda v: "No backup" if v is None else _name(by_id[v]),
              key=f"turkey_backup_{eid}_{pos}")
        st.caption("An eligible saved backup activates only if your starter is officially OUT. The Thursday 1 PM ET lock applies to all three games.")
        submitted = st.form_submit_button(f"Save {pos}", type="primary", use_container_width=True)
    if submitted:
        try:
            if not starter:
                st.warning("Choose a starter before saving.")
            elif backup and starter == backup:
                st.warning("Your emergency backup must be a different player.")
            else:
                service.save_pick(event, str(player["id"]), pos, starter, backup)
                st.toast(f"{pos} saved for Turkey Bowl.")
                st.rerun()
        except Exception as exc:
            _error(exc)
    if complete == 5:
        if st.button("✅ Confirm my Turkey Bowl lineup", use_container_width=True, key="turkey_confirm"):
            try:
                service.confirm(event, str(player["id"]))
                st.success("Turkey Bowl lineup confirmed!")
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
        st.success("🦃🏆 Turkey Bowl Champion: " + ", ".join(r["nickname"] for r in winners))
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
        st.markdown(f"**{r['rank']}. {escape(r['emoji'])} {escape(r['nickname'])}{you}** — {r['score']:.1f} pts")
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
