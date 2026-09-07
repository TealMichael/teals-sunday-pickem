from __future__ import annotations

import importlib
import json
from html import escape
from datetime import datetime, timezone
from typing import Any, Callable

import streamlit as st

import gate4 as _gate4

if getattr(_gate4, "GATE4_LOGIC_SCHEMA_VERSION", 0) < 2:
    _gate4 = importlib.reload(_gate4)

from config import APP_VERSION, NFL_SEASON
from gate4 import (
    add_zero_point_players,
    build_season_standings,
    build_share_summary,
    build_storylines,
    build_weekly_recap,
    build_weekly_leaderboard,
    profile_stats,
)
from validation import validate_single_emoji
from weekly import parse_timestamp

GATE4_UI_SCHEMA_VERSION = 3


def _ordinal(rank: int) -> str:
    if 10 <= rank % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(rank % 10, "th")
    return f"{rank}{suffix}"


def _medal(rank: int) -> str:
    return {1: "🥇", 2: "🥈", 3: "🥉"}.get(int(rank), "")


def render_nav() -> str:
    # v0.4.5 hard-cleans the legacy Leaderboard sub-tab state so the second
    # destination is always a dedicated season-standings screen.
    st.session_state.pop("gate4_subtab", None)
    st.session_state.pop("gate4_leaderboard_subtab", None)
    # Four stable top-level destinations. Keep the stored values unchanged for
    # backward compatibility, but render consistent Material icons instead of
    # platform-dependent emoji. This mirrors native mobile tab-bar guidance:
    # familiar icon + single-word label + persistent selected state.
    options = ["🏈 Sunday", "🏆 Season", "🕘 History", "👤 Profile"]
    nav_labels = {
        "🏈 Sunday": ":material/sports_football: Sunday",
        "🏆 Season": ":material/emoji_events: Season",
        "🕘 History": ":material/history: History",
        "👤 Profile": ":material/person: Profile",
    }
    default = st.session_state.get("gate4_tab") or options[0]
    # v0.4.4 simplifies the app shell: the current-week leaderboard lives on
    # Sunday, while the old Leaderboard destination becomes Season. Preserve a
    # user's old tab intent across the deploy instead of bouncing them to Sunday.
    if default == "🏆 Leaderboard":
        default = "🏆 Season"
        st.session_state.gate4_tab = default
    if default not in options:
        default = options[0]

    # A widget key can survive while the surrounding app mode changes. Normalize
    # stale state before mounting the Gate 4 navigator so Streamlit never has to
    # reconcile a value of the wrong shape/type.
    existing = st.session_state.get("gate4_nav")
    if existing == "🏆 Leaderboard":
        st.session_state.pop("gate4_nav", None)
        existing = None
        default = "🏆 Season"
    elif existing is not None and existing not in options:
        st.session_state.pop("gate4_nav", None)
        existing = None

    segmented = getattr(st, "segmented_control", None)
    if segmented:
        selected = segmented(
            "Navigation",
            options,
            default=None if existing in options else default,
            format_func=lambda option: nav_labels[option],
            key="gate4_nav",
            label_visibility="collapsed",
            required=True,
            width="stretch",
            wrap=False,
        )
    else:
        fallback = st.session_state.get("gate4_nav_fallback")
        if fallback is not None and fallback not in options:
            st.session_state.pop("gate4_nav_fallback", None)
        selected = st.radio(
            "Navigation",
            options,
            index=options.index(default),
            format_func=lambda option: nav_labels[option],
            horizontal=True,
            key="gate4_nav_fallback",
            label_visibility="collapsed",
        )
    selected = selected or default
    st.session_state.gate4_tab = selected
    return selected


def _last_updated(week: dict[str, Any]) -> None:
    stamp = parse_timestamp(week.get("last_data_refresh_at"))
    status = str(week.get("data_status") or "").upper()
    if not stamp:
        if status == "LIVE":
            st.warning("Live scores are waiting for their first refresh. Your lineup is safe.")
        return
    age_minutes = max(0, int((datetime.now(timezone.utc) - stamp).total_seconds() // 60))
    if age_minutes < 1:
        label = "just now"
    elif age_minutes == 1:
        label = "1 minute ago"
    else:
        label = f"{age_minutes} minutes ago"
    st.caption(f"NFL data refreshed {label}.")
    if status == "LIVE" and age_minutes > 45:
        st.warning("Scores may be delayed right now. The last NFL refresh is more than 45 minutes old; no lineup data has been lost.")


def _storylines(bundle: dict[str, Any], leaderboard: list[dict[str, Any]]) -> None:
    story = build_storylines(bundle, leaderboard)
    popular = story.get("most_popular")
    alone = story.get("went_alone") or []
    same = story.get("same_brain") or []

    st.markdown("### Sunday Storylines")
    cards: list[str] = []
    if popular and popular.get("player_name"):
        cards.append(
            f'<div class="story-card"><div class="story-icon">🔥</div><div class="story-title">Most Popular Pick</div><div class="story-main">{escape(str(popular["player_name"]))}</div><div class="small">{int(popular["count"])} of {int(popular["total"])} lineups</div></div>'
        )
    else:
        cards.append('<div class="story-card"><div class="story-icon">🔥</div><div class="story-title">Most Popular Pick</div><div class="small">Waiting for locked lineups.</div></div>')

    if alone:
        item = alone[0]
        more = len(alone) - 1
        more_html = f'<div class="story-more">+ {more} other solo pick{"s" if more != 1 else ""}</div>' if more > 0 else ""
        cards.append(
            f'<div class="story-card"><div class="story-icon">🦄</div><div class="story-title">Went Alone</div><div class="story-main">{escape(str(item["nickname"]))}</div><div class="small">Only one on {escape(str(item["player_name"]))}</div>{more_html}</div>'
        )
    else:
        cards.append('<div class="story-card"><div class="story-icon">🦄</div><div class="story-title">Went Alone</div><div class="small">No solo picks this week.</div></div>')

    if same:
        names = same[0]
        cards.append(
            f'<div class="story-card"><div class="story-icon">👯</div><div class="story-title">Same Brain</div><div class="story-main">{escape(" + ".join(names[:3]))}</div><div class="small">Picked the exact same five</div></div>'
        )
    else:
        cards.append('<div class="story-card"><div class="story-icon">👯</div><div class="story-title">Same Brain</div><div class="small">No identical lineups.</div></div>')

    st.markdown(f'<div class="story-grid">{"".join(cards)}</div>', unsafe_allow_html=True)


def _copy_recap_button(text: str, week_id: str) -> None:
    """Small first-party clipboard helper with a legacy fallback for phones."""
    payload = json.dumps(str(text))
    safe_id = "".join(ch for ch in str(week_id) if ch.isalnum())[:32] or "week"
    st.components.v1.html(
        f"""
<div class="copy-wrap">
  <button id="copy-{safe_id}" type="button">📋 Copy recap for group chat</button>
  <span id="copy-status-{safe_id}" aria-live="polite"></span>
</div>
<style>
  :root {{ color-scheme:light; }}
  html,body {{ margin:0; padding:0; background:transparent; font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
  .copy-wrap {{ display:flex; align-items:center; gap:10px; width:100%; }}
  button {{ flex:1; min-height:44px; border:1px solid #0F766E; border-radius:12px; background:#0F766E; color:#fff; font-size:14px; font-weight:800; cursor:pointer; }}
  span {{ color:#155E56; font-size:12px; font-weight:750; white-space:nowrap; }}
</style>
<script>
const text = {payload};
const button = document.getElementById("copy-{safe_id}");
const status = document.getElementById("copy-status-{safe_id}");
async function copyText() {{
  let copied = false;
  try {{ await navigator.clipboard.writeText(text); copied = true; }} catch (err) {{}}
  if (!copied) {{
    const area = document.createElement("textarea");
    area.value = text; area.style.position = "fixed"; area.style.opacity = "0";
    document.body.appendChild(area); area.focus(); area.select();
    try {{ copied = document.execCommand("copy"); }} catch (err) {{ copied = false; }}
    document.body.removeChild(area);
  }}
  status.textContent = copied ? "Copied!" : "Select the text below to copy.";
  if (copied) setTimeout(() => status.textContent = "", 1800);
}}
button.addEventListener("click", copyText);
</script>
        """,
        height=50,
    )


def _weekly_recap(store, week: dict[str, Any], bundle: dict[str, Any], leaderboard: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    season_results = store.get_weekly_results(season=int(week.get("season") or NFL_SEASON))
    season = add_zero_point_players(build_season_standings(season_results), store.get_registered_players())
    recap = build_weekly_recap(
        bundle,
        leaderboard,
        season_results,
        current_week=int(week.get("nfl_week") or 0),
    )

    champions = list(recap.get("champions") or [])
    if champions:
        names = " + ".join(str(row.get("nickname") or "Champion") for row in champions)
        score = float(champions[0].get("score") or 0)
        title = "Co-Champions" if len(champions) > 1 else "Champion"
        st.markdown(
            f'<div class="recap-hero"><div class="recap-kicker">🏆 WEEKLY {escape(title.upper())}</div><div class="recap-champion">{escape(names)}</div><div class="recap-score">{score:.1f} points</div></div>',
            unsafe_allow_html=True,
        )

    cards: list[str] = []
    popular = recap.get("most_popular")
    if popular and popular.get("player_name"):
        cards.append(
            f'<div class="recap-card"><div class="story-icon">🔥</div><div class="story-title">Most Popular</div><div class="story-main">{escape(str(popular["player_name"]))}</div><div class="small">{int(popular["count"])} of {int(popular["total"])} lineups</div></div>'
        )

    solo = recap.get("boldest_solo")
    if solo:
        cards.append(
            f'<div class="recap-card"><div class="story-icon">🦄</div><div class="story-title">Boldest Solo</div><div class="story-main">{escape(str(solo["nickname"]))}</div><div class="small">Only one on {escape(str(solo["player_name"]))} • {float(solo["points"]):.1f} pts</div></div>'
        )
    else:
        cards.append('<div class="recap-card"><div class="story-icon">🦄</div><div class="story-title">Boldest Solo</div><div class="small">No solo picks this week.</div></div>')

    closest = recap.get("closest_finish")
    if closest:
        if closest.get("tied"):
            closest_main = f'{escape(str(closest["upper"]))} + {escape(str(closest["lower"]))}'
            closest_small = f'Dead heat at {float(closest["upper_score"]):.1f}'
        else:
            closest_main = f'{escape(str(closest["upper"]))} over {escape(str(closest["lower"]))}'
            closest_small = f'Just {float(closest["gap"]):.1f} points apart'
        cards.append(
            f'<div class="recap-card"><div class="story-icon">🤏</div><div class="story-title">Closest Finish</div><div class="story-main">{closest_main}</div><div class="small">{closest_small}</div></div>'
        )

    same = recap.get("same_brain") or []
    if same:
        cards.append(
            f'<div class="recap-card"><div class="story-icon">👯</div><div class="story-title">Same Brain</div><div class="story-main">{escape(" + ".join(str(name) for name in same[:3]))}</div><div class="small">Picked the exact same five</div></div>'
        )
    else:
        cards.append('<div class="recap-card"><div class="story-icon">👯</div><div class="story-title">Same Brain</div><div class="small">No identical lineups this week.</div></div>')

    mover = recap.get("biggest_mover")
    if mover and mover.get("movers"):
        names = " + ".join(str(row.get("nickname") or "Player") for row in mover["movers"][:3])
        places = int(mover.get("places") or 0)
        cards.append(
            f'<div class="recap-card"><div class="story-icon">📈</div><div class="story-title">Biggest Mover</div><div class="story-main">{escape(names)}</div><div class="small">Up {places} place{"s" if places != 1 else ""} in the season race</div></div>'
        )
    elif int(week.get("nfl_week") or 0) <= 1:
        cards.append('<div class="recap-card"><div class="story-icon">📈</div><div class="story-title">Season Race</div><div class="story-main">And we’re off</div><div class="small">Week 1 sets the starting order.</div></div>')
    else:
        cards.append('<div class="recap-card"><div class="story-icon">📈</div><div class="story-title">Biggest Mover</div><div class="small">No one climbed the season standings this week.</div></div>')

    st.markdown("### Week in Review")
    st.markdown(f'<div class="recap-grid">{"".join(cards)}</div>', unsafe_allow_html=True)

    share_text = build_share_summary(week, recap, leaderboard, season)
    with st.expander("📤 Share Results", expanded=False):
        st.caption("Copy this clean recap into the group chat.")
        _copy_recap_button(share_text, str(week.get("id") or week.get("nfl_week") or "week"))
        st.code(share_text, language=None)
    return season, recap


def _render_roster_detail(row: dict[str, Any], current_player_id: str) -> None:
    is_self = str(row.get("player_id")) == str(current_player_id)
    with st.container(border=True):
        st.markdown(f"#### {row.get('emoji','🏈')} {row.get('nickname','Player')} • {float(row.get('score') or 0):.1f} pts")
        st.caption("Tap the same leaderboard row again to close.")
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
                        detail_text = component.get("text") if isinstance(component, dict) else None
                        if detail_text:
                            st.write(str(detail_text))


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
    if detail:
        st.caption("Tap any player to see their five and scoring details.")

    selected_id = str(st.session_state.get("gate4_detail_player_id") or "")
    for row in leaderboard:
        rank = int(row.get("rank") or 0)
        row_player_id = str(row.get("player_id") or "")
        is_self = row_player_id == str(current_player_id)
        medal = _medal(rank)
        prefix = f"{medal} " if medal else ""
        label = f"{prefix}{rank}. {row.get('emoji','🏈')} {row.get('nickname','Player')}  ·  {float(row.get('score') or 0):.1f} pts"
        if is_self:
            label += "  ← YOU"
        if st.button(label, key=f"leaderbtn_{row.get('lineup_id')}", use_container_width=True):
            if detail:
                if selected_id == row_player_id:
                    st.session_state.pop("gate4_detail_player_id", None)
                else:
                    st.session_state.gate4_detail_player_id = row_player_id
                st.rerun()
        if detail and selected_id == row_player_id:
            _render_roster_detail(row, current_player_id)


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
    season: list[dict[str, Any]] = []
    if data_status == "FINAL":
        season, _ = _weekly_recap(store, week, bundle, leaderboard)
    elif show_storylines:
        _storylines(bundle, leaderboard)
    st.markdown("### Standings")
    _leaderboard_rows(leaderboard, str(player["id"]), detail=True)
    if data_status == "FINAL":
        if season:
            leader = season[0]
            own = next((row for row in season if str(row.get("player_id")) == str(player.get("id"))), None)
            own_text = f"You: {_ordinal(int(own['rank']))} — {int(own['season_points'])} pts" if own else ""
            st.markdown(
                f'<div class="card-tight"><div class="eyebrow">Season Leader</div><strong>{escape(str(leader.get("emoji") or "🏆"))} {escape(str(leader.get("nickname") or "Leader"))} — {int(leader.get("season_points") or 0)} pts</strong><div class="small">{escape(own_text)}</div></div>',
                unsafe_allow_html=True,
            )
    _last_updated(week)


def _render_season_rows(standings: list[dict[str, Any]], current_player_id: str | None = None) -> None:
    if not standings:
        st.info("Season standings will appear after the first finalized Sunday.")
        return
    for row in standings:
        rank = int(row.get("rank") or 0)
        is_self = current_player_id is not None and str(row.get("player_id")) == str(current_player_id)
        you = '<span class="you-badge">YOU</span>' if is_self else ""
        st.markdown(
            f'<div class="season-row"><div class="season-left"><div class="season-name">{_medal(rank)} {rank}. {escape(str(row.get("emoji") or "🏈"))} {escape(str(row.get("nickname") or "Player"))} {you}</div><div class="small">{float(row.get("total_fantasy_points") or 0):.1f} total fantasy pts</div></div><div class="season-points">{int(row.get("season_points") or 0)} pts</div></div>',
            unsafe_allow_html=True,
        )


def _profile_stat_grid(stats: dict[str, Any]) -> None:
    items = [
        ("🏆", "Wins", str(int(stats.get("wins") or 0))),
        ("🥈", "Seconds", str(int(stats.get("seconds") or 0))),
        ("🥉", "Thirds", str(int(stats.get("thirds") or 0))),
        ("⭐", "Season Points", str(int(stats.get("season_points") or 0))),
        ("🏈", "Fantasy Points", f"{float(stats.get('total_fantasy_points') or 0):.1f}"),
    ]
    html = ''.join(
        f'<div class="profile-stat"><div class="profile-stat-icon">{icon}</div><div class="profile-stat-value">{escape(value)}</div><div class="profile-stat-label">{escape(label)}</div></div>'
        for icon, label, value in items
    )
    st.markdown(f'<div class="profile-grid">{html}</div>', unsafe_allow_html=True)


def render_leaderboards(store, week: dict[str, Any], player: dict[str, Any], phase: str) -> None:
    """Render the season championship destination.

    The current-week leaderboard intentionally lives on Sunday after the 1 PM
    lock, so this top-level destination has one job: season standings. Keeping
    this function name avoids churn in the Gate 4 integration layer.
    """
    st.markdown("### Season")
    results = store.get_weekly_results(season=int(week.get("season") or NFL_SEASON))
    standings = add_zero_point_players(build_season_standings(results), store.get_registered_players())
    if not results:
        st.caption("Season points begin after Week 1 becomes FINAL on Monday.")
    _render_season_rows(standings, str(player.get("id")))
    with st.expander("ⓘ How season points work"):
        st.write("1st 12 • 2nd 9 • 3rd 7 • 4th 6 • 5th 5 • 6th 4 • 7th 3 • 8th 2 • 9th 1 • 10th+ 0")
        st.caption("Ties receive the full points for that rank; the next rank skips appropriately.")

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
    _profile_stat_grid(stats)

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

    with st.expander("Add to Home Screen"):
        st.markdown("**iPhone/iPad (Safari):** Share → **Add to Home Screen**.\n\n**Android (Chrome):** Menu → **Add to Home screen** or **Install app** if offered.")
        st.caption("Optional, but it makes Sunday Pick'em feel much more like a regular phone app. Notifications are not required for Week 1.")

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
    elif tab == "🏆 Season":
        st.markdown("### Season Standings")
        demo_results = []
        for row in leaderboard:
            demo_results.append({
                "player_id": row["player_id"], "nickname_snapshot": row["nickname"], "emoji_snapshot": row["emoji"],
                "season_points": row["season_points_if_final"], "weekly_score": row["score"], "finish_rank": row["rank"],
            })
        _render_season_rows(build_season_standings(demo_results), demo_player_id)
        st.caption("Demo season standings use the exact weekly placement points that will feed the real season leaderboard.")
    elif tab == "🕘 History":
        st.markdown("### History")
        st.markdown(
            '<div class="history-card"><div class="history-head"><div><div class="eyebrow">Final</div><div class="week-title">Week 3</div></div><div class="small">View final standings</div></div>'
            '<div class="history-row"><span>🥇 🦅 Jenny</span><strong>91.4</strong></div>'
            '<div class="history-row"><span>🥈 🤘 Mike T.</span><strong>87.2</strong></div>'
            '<div class="history-row"><span>🥉 🐺 Alan</span><strong>81.9</strong></div></div>',
            unsafe_allow_html=True,
        )
        st.caption("Production history keeps final standings but removes detailed rosters after the next Tuesday pool publishes.")
    else:
        st.markdown(f"### {demo_player.get('emoji')} {demo_player.get('nickname')}")
        _profile_stat_grid({"wins": 3, "seconds": 2, "thirds": 1, "season_points": 68, "total_fantasy_points": 842.7})
        _how_to_play()
        st.markdown("#### Trophy Case")
        st.markdown('<div class="card-tight"><strong>🏆 2026 Champion</strong><div class="small">Awarded after the regular-season finale.</div></div>', unsafe_allow_html=True)

