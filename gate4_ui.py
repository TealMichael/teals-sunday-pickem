from __future__ import annotations

from html import escape
from typing import Any, Callable

import streamlit as st

from config import APP_VERSION, NFL_SEASON
from gate4 import (
    add_zero_point_players,
    build_season_standings,
    build_storylines,
    build_weekly_leaderboard,
    profile_stats,
)
from validation import validate_single_emoji


def _ordinal(rank: int) -> str:
    if 10 <= rank % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(rank % 10, "th")
    return f"{rank}{suffix}"


def _medal(rank: int) -> str:
    return {1: "🥇", 2: "🥈", 3: "🥉"}.get(int(rank), "")


def render_nav() -> str:
    options = ["🏈 Sunday", "🏆 Leaderboard", "🕘 History", "👤 Profile"]
    default = st.session_state.get("gate4_tab") or options[0]
    if default not in options:
        default = options[0]

    # A widget key can survive while the surrounding app mode changes. Normalize
    # stale state before mounting the Gate 4 navigator so Streamlit never has to
    # reconcile a value of the wrong shape/type.
    existing = st.session_state.get("gate4_nav")
    if existing is not None and existing not in options:
        st.session_state.pop("gate4_nav", None)
        existing = None

    segmented = getattr(st, "segmented_control", None)
    if segmented:
        selected = segmented(
            "Navigation",
            options,
            default=None if existing in options else default,
            key="gate4_nav",
            label_visibility="collapsed",
        )
    else:
        fallback = st.session_state.get("gate4_nav_fallback")
        if fallback is not None and fallback not in options:
            st.session_state.pop("gate4_nav_fallback", None)
        selected = st.radio(
            "Navigation",
            options,
            index=options.index(default),
            horizontal=True,
            key="gate4_nav_fallback",
            label_visibility="collapsed",
        )
    selected = selected or default
    st.session_state.gate4_tab = selected
    return selected


def _last_updated(week: dict[str, Any]) -> None:
    stamp = week.get("last_data_refresh_at")
    if stamp:
        st.caption(f"NFL data last refreshed: {stamp}")


def _storylines(bundle: dict[str, Any], leaderboard: list[dict[str, Any]]) -> None:
    story = build_storylines(bundle, leaderboard)
    popular = story.get("most_popular")
    alone = story.get("went_alone") or []
    same = story.get("same_brain") or []

    st.markdown("### Sunday Storylines")
    cols = st.columns(3)
    with cols[0]:
        if popular and popular.get("player_name"):
            st.markdown(
                f'<div class="story-card"><div class="story-icon">🔥</div><div class="story-title">Most Popular Pick</div><div class="story-main">{escape(str(popular["player_name"]))}</div><div class="small">{int(popular["count"])} of {int(popular["total"])} lineups</div></div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown('<div class="story-card"><div class="story-icon">🔥</div><div class="story-title">Most Popular Pick</div><div class="small">Waiting for locked lineups.</div></div>', unsafe_allow_html=True)
    with cols[1]:
        if alone:
            item = alone[0]
            more = len(alone) - 1
            extra = f" + {more} more" if more > 0 else ""
            st.markdown(
                f'<div class="story-card"><div class="story-icon">🦄</div><div class="story-title">Went Alone</div><div class="story-main">{escape(str(item["nickname"]))}</div><div class="small">only one on {escape(str(item["player_name"]))}{extra}</div></div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown('<div class="story-card"><div class="story-icon">🦄</div><div class="story-title">Went Alone</div><div class="small">No solo picks this week.</div></div>', unsafe_allow_html=True)
    with cols[2]:
        if same:
            names = same[0]
            st.markdown(
                f'<div class="story-card"><div class="story-icon">👯</div><div class="story-title">Same Brain</div><div class="story-main">{escape(" + ".join(names[:3]))}</div><div class="small">picked the exact same five</div></div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown('<div class="story-card"><div class="story-icon">👯</div><div class="story-title">Same Brain</div><div class="small">No identical lineups.</div></div>', unsafe_allow_html=True)


def _render_roster_detail(row: dict[str, Any], current_player_id: str) -> None:
    is_self = str(row.get("player_id")) == str(current_player_id)
    st.markdown(f"#### {row.get('emoji','🏈')} {row.get('nickname','Player')} • {float(row.get('score') or 0):.1f}")
    for roster in row.get("roster") or []:
        pos = str(roster.get("position") or "")
        if roster.get("missing"):
            st.markdown(
                f'<div class="score-row"><span class="position-pill">{escape(pos)}</span><div class="score-body"><strong>Missing position</strong><div class="small">Scores 0.0</div></div><div class="score-points">0.0</div></div>',
                unsafe_allow_html=True,
            )
            continue
        player = roster.get("player") or {}
        starter = roster.get("starter") or {}
        backup = roster.get("backup") or {}
        name = str(player.get("player_name") or "Player")
        emergency = bool(roster.get("emergency_activated"))
        status = str(roster.get("game_status_text") or "")
        meta = f"{player.get('team_abbr','')} vs {player.get('opponent_abbr','')}"
        if emergency:
            meta = f"🚨 Emergency activated for {starter.get('player_name','starter')} • {meta}"
        elif is_self and backup:
            meta = f"{meta} • Emergency: {backup.get('player_name')} (private)"
        st.markdown(
            f'<div class="score-row"><span class="position-pill">{escape(pos)}</span><div class="score-body"><strong>{escape(name)}</strong><div class="small">{escape(meta)}</div><div class="small">{escape(status)}</div></div><div class="score-points">{float(roster.get("points") or 0):.1f}</div></div>',
            unsafe_allow_html=True,
        )
        breakdown = player.get("score_breakdown") or {}
        if breakdown:
            with st.expander(f"{pos} scoring details"):
                for component in breakdown.values():
                    text = component.get("text") if isinstance(component, dict) else None
                    if text:
                        st.write(str(text))


def _leaderboard_rows(leaderboard: list[dict[str, Any]], current_player_id: str, *, detail: bool = True) -> None:
    if not leaderboard:
        st.info("No one has a lineup in this week yet.")
        return
    own = next((row for row in leaderboard if str(row.get("player_id")) == str(current_player_id)), None)
    if own:
        st.markdown(
            f'<div class="you-strip"><strong>You: {_ordinal(int(own["rank"]))}</strong><span>{float(own["score"]):.1f} pts</span></div>',
            unsafe_allow_html=True,
        )

    for row in leaderboard:
        rank = int(row.get("rank") or 0)
        is_self = str(row.get("player_id")) == str(current_player_id)
        label = f"{_medal(rank)} {rank}. {row.get('emoji','🏈')} {row.get('nickname','Player')}    {float(row.get('score') or 0):.1f}"
        if is_self:
            label += "   ← YOU"
        if st.button(label, key=f"leaderbtn_{row.get('lineup_id')}", use_container_width=True):
            st.session_state.gate4_detail_player_id = str(row.get("player_id"))
    if detail:
        selected_id = st.session_state.get("gate4_detail_player_id")
        selected = next((row for row in leaderboard if str(row.get("player_id")) == str(selected_id)), None)
        if selected:
            st.markdown("---")
            _render_roster_detail(selected, current_player_id)


def render_live_sunday(store, week: dict[str, Any], player: dict[str, Any], *, show_storylines: bool = True) -> None:
    bundle = store.get_week_public_bundle(str(week["id"]))
    leaderboard = build_weekly_leaderboard(bundle)
    data_status = str(week.get("data_status") or "LIVE").upper()
    title = "Final Results" if data_status == "FINAL" else ("Provisional Results" if data_status == "PROVISIONAL" else "Live Sunday")
    st.markdown(f"### {title}")
    if data_status == "PROVISIONAL":
        st.caption("Sunday scoring is complete, but results stay provisional until Monday reconciliation.")
    elif data_status == "FINAL":
        st.caption("Monday reconciliation is complete. These results are FINAL.")
    else:
        st.caption("Scores refresh automatically during Sunday games.")
    if show_storylines:
        _storylines(bundle, leaderboard)
    st.markdown("### Standings")
    _leaderboard_rows(leaderboard, str(player["id"]), detail=True)
    if data_status == "FINAL":
        season_results = store.get_weekly_results(season=int(week.get("season") or NFL_SEASON))
        season = add_zero_point_players(build_season_standings(season_results), store.get_registered_players())
        if season:
            leader = season[0]
            own = next((row for row in season if str(row.get("player_id")) == str(player.get("id"))), None)
            own_text = f"You: {_ordinal(int(own['rank']))} — {int(own['season_points'])} pts" if own else ""
            st.markdown(
                f'<div class="card-tight"><div class="eyebrow">Season Leader</div><strong>{escape(str(leader.get("emoji") or "🏆"))} {escape(str(leader.get("nickname") or "Leader"))} — {int(leader.get("season_points") or 0)} pts</strong><div class="small">{escape(own_text)}</div></div>',
                unsafe_allow_html=True,
            )
    _last_updated(week)


def render_leaderboards(store, week: dict[str, Any], player: dict[str, Any], phase: str) -> None:
    weekly_tab, season_tab = st.tabs(["This Week", "Season"])
    with weekly_tab:
        if phase != "locked":
            registered = store.get_registered_players()
            bundle = store.get_week_public_bundle(str(week["id"])) if week.get("published_at") else {"lineups": []}
            ready = sum(1 for row in bundle.get("lineups") or [] if row.get("confirmed_at"))
            st.markdown("### Weekly Leaderboard")
            st.metric("Lineups ready", f"{ready} / {len(registered)}")
            st.caption("Lineups stay private until Sunday at 1:00 PM ET.")
        else:
            bundle = store.get_week_public_bundle(str(week["id"]))
            leaderboard = build_weekly_leaderboard(bundle)
            st.markdown("### Weekly Leaderboard")
            _leaderboard_rows(leaderboard, str(player["id"]), detail=True)
            _last_updated(week)

    with season_tab:
        st.markdown("### Season Standings")
        results = store.get_weekly_results(season=int(week.get("season") or NFL_SEASON))
        standings = add_zero_point_players(build_season_standings(results), store.get_registered_players())
        if not results:
            st.caption("Season points begin after Week 1 becomes FINAL on Monday.")
        for row in standings:
            rank = int(row.get("rank") or 0)
            suffix = " ← YOU" if str(row.get("player_id")) == str(player.get("id")) else ""
            st.markdown(
                f'<div class="season-row"><div><strong>{_medal(rank)} {rank}. {escape(str(row.get("emoji") or "🏈"))} {escape(str(row.get("nickname") or "Player"))}{suffix}</strong><div class="small">{float(row.get("total_fantasy_points") or 0):.1f} total fantasy pts</div></div><div class="season-points">{int(row.get("season_points") or 0)} pts</div></div>',
                unsafe_allow_html=True,
            )
        popover = getattr(st, "popover", None)
        if popover:
            with popover("ⓘ Season points"):
                st.write("1st 12 • 2nd 9 • 3rd 7 • 4th 6 • 5th 5 • 6th 4 • 7th 3 • 8th 2 • 9th 1 • 10th+ 0")
                st.caption("Ties receive the full points for that rank; the next rank skips appropriately.")
        else:
            st.caption("ⓘ Season points: 12–9–7–6–5–4–3–2–1 for 1st through 9th. Ties receive the full points for that rank.")


def render_history(store, season: int) -> None:
    st.markdown("### History")
    results = store.get_weekly_results(season=season)
    if not results:
        st.info("Your first finalized Sunday will appear here Monday morning.")
        return
    by_week: dict[int, list[dict[str, Any]]] = {}
    for row in results:
        by_week.setdefault(int(row.get("nfl_week") or 0), []).append(row)
    for nfl_week in sorted(by_week, reverse=True):
        rows = sorted(by_week[nfl_week], key=lambda r: (int(r.get("finish_rank") or 999), str(r.get("nickname_snapshot") or "").casefold()))
        with st.expander(f"Week {nfl_week}", expanded=nfl_week == max(by_week)):
            for row in rows:
                rank = int(row.get("finish_rank") or 0)
                st.markdown(
                    f'<div class="history-row"><span>{_medal(rank)} {rank}. {escape(str(row.get("emoji_snapshot") or "🏈"))} {escape(str(row.get("nickname_snapshot") or "Player"))}</span><strong>{float(row.get("weekly_score") or 0):.1f}</strong></div>',
                    unsafe_allow_html=True,
                )
            st.caption("Detailed weekly rosters are intentionally removed after the next Tuesday pool publishes.")


def _how_to_play() -> None:
    with st.expander("How to Play"):
        st.markdown(
            """
**Pick five:** one QB, RB, WR, TE, and K from the shared weekly choices. Duplicate picks are allowed.

**Eligible games:** Sunday games beginning at 1:00 PM ET or later, including Sunday Night Football. Thursday, Monday, Saturday/holiday, and Sunday-morning international games do not count.

**Lock:** every lineup locks Sunday at exactly 1:00 PM ET. Missing positions score 0.

**Scoring:** half-PPR with fractional scoring. Passing: 1/25 yds, 4/pass TD, -2/INT. Rushing/receiving: 1/10 yds, 6/TD, 0.5/reception. Fumble lost -2. Two-point conversion 2. Return TD 6. Kicker: every made FG 3, made XP 1, misses 0.

**Questionable players:** you may choose a healthy emergency backup from the same position pool. If the starter is later ruled OUT/inactive and does not play, the backup activates. If the starter plays, the starter counts. Emergency picks stay private unless they activate.

**Weekly ties:** ties are allowed. Tied players receive the full season points for that rank; the next rank skips appropriately.

**Season points:** 1st 12, 2nd 9, 3rd 7, then 6–5–4–3–2–1 through 9th. Season standings sort by season points, then total fantasy points. A remaining season tie means co-champions.

**Final:** Sunday-night results are provisional. Monday reconciliation makes the week FINAL.
            """
        )


def render_profile(store, player: dict[str, Any], season: int, on_sign_out: Callable[[], None] | None) -> None:
    st.markdown(f"### {player.get('emoji','🏈')} {player.get('nickname','Player')}")
    results = store.get_weekly_results(season=season, player_id=str(player["id"]))
    stats = profile_stats(str(player["id"]), results)
    cols = st.columns(3)
    with cols[0]:
        st.metric("🏆 Wins", int(stats["wins"]))
    with cols[1]:
        st.metric("🥈 Seconds", int(stats["seconds"]))
    with cols[2]:
        st.metric("🥉 Thirds", int(stats["thirds"]))
    st.metric("Season Points", int(stats["season_points"]))
    st.metric("Total Fantasy Points", f"{float(stats['total_fantasy_points']):.1f}")

    with st.expander("Change emoji"):
        new_emoji = st.text_input("Choose one emoji", value=str(player.get("emoji") or "🏈"), max_chars=8, key="profile_emoji")
        if st.button("Save Emoji", use_container_width=True):
            ok, message = validate_single_emoji(new_emoji)
            if not ok:
                st.error(message)
            else:
                updated = store.update_player_emoji(str(player["id"]), new_emoji.strip())
                if updated:
                    st.session_state.player = updated
                st.toast("Emoji updated.")
                st.rerun()

    _how_to_play()
    st.markdown("#### Trophy Case")
    champions = store.get_season_champions()
    if champions:
        by_season: dict[int, list[dict[str, Any]]] = {}
        for row in champions:
            by_season.setdefault(int(row.get("season") or 0), []).append(row)
        for champ_season in sorted(by_season, reverse=True):
            names = " + ".join(f"{row.get('emoji_snapshot','🏆')} {row.get('nickname_snapshot','Champion')}" for row in by_season[champ_season])
            st.markdown(f'<div class="card-tight"><strong>🏆 {champ_season} Champion</strong><div class="small">{escape(names)}</div></div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="card-tight"><strong>🏆 {season} Champion</strong><div class="small">Awarded after the regular-season finale.</div></div>', unsafe_allow_html=True)

    st.caption(f"Build {APP_VERSION}")
    if on_sign_out:
        st.button("Sign Out", key="profile_signout", type="secondary", use_container_width=True, on_click=on_sign_out)


def maybe_render_final_celebration(store, week: dict[str, Any], player: dict[str, Any]) -> None:
    if str(week.get("data_status") or "").upper() != "FINAL":
        return
    results = store.get_weekly_results(week_id=str(week["id"]))
    if not results:
        return
    key = f"celebrated::{week['id']}"
    if st.session_state.get(key):
        return
    st.session_state[key] = True
    champions = [row for row in results if bool(row.get("is_champion"))]
    if not champions:
        return
    names = " + ".join(str(row.get("nickname_snapshot") or "Champion") for row in champions)
    score = float(champions[0].get("weekly_score") or 0)
    earned = int(champions[0].get("season_points") or 0)
    own = next((row for row in results if str(row.get("player_id")) == str(player.get("id"))), None)
    own_text = f"You finished {_ordinal(int(own['finish_rank']))} with {float(own['weekly_score']):.1f}." if own else ""
    footballs = "".join(f'<span class="football f{i}">🏈</span>' for i in range(24))
    title = "CO-CHAMPIONS" if len(champions) > 1 else "WEEKLY CHAMPION"
    st.markdown(
        f'''<div class="champion-overlay">{footballs}<div class="champion-card"><div class="eyebrow">{title}</div><div class="champion-name">🏆 {escape(names)}</div><div class="champion-score">{score:.1f} points • +{earned} season pts</div><div class="small">{escape(own_text)}</div></div></div>''',
        unsafe_allow_html=True,
    )


def _demo_bundle() -> dict[str, Any]:
    names = [
        ("demo-a", "Jenny", "🦅"), ("demo-b", "Mike T.", "🤘"), ("demo-c", "Alan", "🐺"),
        ("demo-d", "Chris", "🦬"), ("demo-e", "Sarah", "🔥"), ("demo-f", "Nate", "🦈"),
        ("demo-g", "Emily", "🌙"), ("demo-h", "Ryan", "🧀"),
    ]
    pool = []
    for pos_idx, pos in enumerate(("QB","RB","WR","TE","K")):
        for slot in range(1, 6):
            pid = f"{pos}-{slot}"
            pool.append({
                "id": pid, "position": pos, "player_name": f"Demo {pos} {slot}", "team_abbr": "DET",
                "opponent_abbr": "GB", "availability_status": "HEALTHY", "score_total": float(8 + pos_idx*2 + slot),
                "score_breakdown": {"demo": {"text": f"Demo scoring — +{8 + pos_idx*2 + slot:.1f}"}}, "game_status": "LIVE",
            })
    players = [{"id": pid, "nickname": name, "emoji": emoji} for pid, name, emoji in names]
    lineups = []
    picks = []
    patterns = [
        [1,1,1,1,1], [1,2,2,2,2], [1,2,3,3,3], [2,2,2,2,2],
        [3,3,3,3,3], [4,4,4,4,4], [5,5,5,5,5], [5,5,5,5,5],
    ]
    for idx, (pid, _, _) in enumerate(names):
        lid = f"lineup-{idx}"
        lineups.append({"id": lid, "player_id": pid, "confirmed_at": "demo"})
        for pos, slot in zip(("QB","RB","WR","TE","K"), patterns[idx]):
            picks.append({"lineup_id": lid, "position": pos, "pool_player_id": f"{pos}-{slot}", "emergency_pool_player_id": None})
    return {"players": players, "lineups": lineups, "picks": picks, "pool": pool, "games": []}


def render_gate4_demo(current_player: dict[str, Any] | None = None) -> None:
    st.markdown('<div class="status-test"><strong>Gate 4 Demo Mode</strong><br>Synthetic lineups and scores only. Nothing here touches Week 1.</div>', unsafe_allow_html=True)
    top1, top2, top3 = st.columns(3)
    with top1:
        if st.button("Live Demo", use_container_width=True):
            st.session_state.gate4_demo_phase = "live"
            st.rerun()
    with top2:
        if st.button("Final Demo", use_container_width=True):
            st.session_state.gate4_demo_phase = "final"
            st.session_state.pop("gate4_demo_final_seen", None)
            st.rerun()
    with top3:
        if st.button("Exit Demo", use_container_width=True):
            st.session_state.gate4_demo = False
            st.session_state.gate4_demo_phase = "live"
            st.session_state.gate4_tab = "🏈 Sunday"
            st.session_state.pop("gate4_nav", None)
            st.session_state.pop("gate4_nav_fallback", None)
            st.session_state.pop("gate4_detail_player_id", None)
            # Commissioner remains authenticated; exit returns to the admin hub.
            st.rerun()

    phase = st.session_state.get("gate4_demo_phase") or "live"
    bundle = _demo_bundle()
    leaderboard = build_weekly_leaderboard(bundle)
    demo_player_id = "demo-b"
    current_player = current_player if isinstance(current_player, dict) else {}
    demo_player = {
        "id": demo_player_id,
        "nickname": current_player.get("nickname") or "Mike T.",
        "emoji": current_player.get("emoji") or "🤘",
    }

    if phase == "final" and not st.session_state.get("gate4_demo_final_seen"):
        st.session_state.gate4_demo_final_seen = True
        champions = [row for row in leaderboard if int(row.get("rank") or 0) == 1]
        names = " + ".join(str(row.get("nickname")) for row in champions)
        score = float(champions[0].get("score") or 0) if champions else 0
        footballs = "".join(f'<span class="football f{i}">🏈</span>' for i in range(24))
        st.markdown(
            f'<div class="champion-overlay">{footballs}<div class="champion-card"><div class="eyebrow">CO-CHAMPIONS</div><div class="champion-name">🏆 {escape(names)}</div><div class="champion-score">{score:.1f} points • +12 season pts</div><div class="small">Demo celebration only</div></div></div>',
            unsafe_allow_html=True,
        )

    tab = render_nav()
    if tab == "🏈 Sunday":
        st.markdown("### " + ("Final Results" if phase == "final" else "Live Sunday"))
        _storylines(bundle, leaderboard)
        st.markdown("### Standings")
        _leaderboard_rows(leaderboard, demo_player_id, detail=True)
        if phase == "final":
            st.caption("Demo includes a first-place tie, traditional competition ranking, and full season points for tied champions.")
    elif tab == "🏆 Leaderboard":
        st.markdown("### Weekly Leaderboard")
        _leaderboard_rows(leaderboard, demo_player_id, detail=True)
        st.markdown("### Season Preview")
        demo_results = []
        for row in leaderboard:
            demo_results.append({
                "player_id": row["player_id"], "nickname_snapshot": row["nickname"], "emoji_snapshot": row["emoji"],
                "season_points": row["season_points_if_final"], "weekly_score": row["score"], "finish_rank": row["rank"],
            })
        for row in build_season_standings(demo_results):
            st.markdown(f"{_medal(int(row['rank']))} **{row['rank']}. {row['emoji']} {row['nickname']}** — {row['season_points']} pts")
    elif tab == "🕘 History":
        st.markdown("### History Preview")
        st.markdown("🥇 Jenny — 91.4  \n🥈 Mike T. — 87.2  \n🥉 Alan — 81.9")
        st.caption("Production history keeps final standings but removes detailed rosters after the next Tuesday pool publishes.")
    else:
        st.markdown(f"### {demo_player.get('emoji')} {demo_player.get('nickname')}")
        st.metric("🏆 Wins", 3)
        st.metric("🥈 Seconds", 2)
        st.metric("🥉 Thirds", 1)
        st.metric("Season Points", 68)
        st.metric("Total Fantasy Points", "842.7")
        _how_to_play()

