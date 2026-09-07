from __future__ import annotations

from typing import Any

import streamlit as st

from gate6 import launch_readiness, run_full_week_rehearsal

GATE6_UI_SCHEMA_VERSION = 1

_STATUS_ICON = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}


def _render_check(row: dict[str, Any]) -> None:
    status = str(row.get("status") or "WARN")
    icon = _STATUS_ICON.get(status, "•")
    with st.container(border=True):
        left, right = st.columns([5, 1])
        with left:
            st.markdown(f"**{icon} {row.get('title') or 'Check'}**")
            st.caption(str(row.get("detail") or ""))
        with right:
            st.markdown(f"**{status}**")


def _render_launch_report(report: dict[str, Any]) -> None:
    overall = str(report.get("overall") or "WARN")
    if overall == "READY":
        st.success("Week 1 launch check: READY. All required systems are green.")
    elif overall == "WARN":
        st.warning("Week 1 launch check: READY WITH WARNINGS. Review the yellow items before game day.")
    else:
        st.error("Week 1 launch check: NOT READY. Fix the red item(s) before inviting the group.")
    for row in report.get("checks") or []:
        _render_check(row)


def _render_rehearsal(report: dict[str, Any]) -> None:
    if bool(report.get("success")):
        st.success(f"Full-week rehearsal passed {int(report.get('passed') or 0)}/{int(report.get('total') or 0)} checks.")
    else:
        st.error(f"Full-week rehearsal failed. {int(report.get('passed') or 0)}/{int(report.get('total') or 0)} checks passed.")
    for step in report.get("steps") or []:
        icon = _STATUS_ICON.get(str(step.get("status") or "FAIL"), "•")
        st.markdown(f"{icon} **{step.get('name')}** — {step.get('detail')}")


def render_launch_readiness(store, week: dict[str, Any]) -> None:
    st.markdown("#### Launch Readiness")
    st.caption("Production-safe checks only. Nothing on this screen publishes a pool, changes a lineup, or edits a score.")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Run Launch Check", type="primary", use_container_width=True, key="g6_launch_check"):
            try:
                with st.spinner("Checking Week 1 systems…"):
                    st.session_state.g6_launch_report = launch_readiness(store, week)
                st.toast("Launch check complete.")
            except Exception as exc:
                st.session_state.g6_launch_report = None
                st.error(f"Launch check could not complete: {exc}")
    with c2:
        if st.button("Run Full Week Rehearsal", use_container_width=True, key="g6_rehearsal"):
            st.session_state.g6_rehearsal_report = run_full_week_rehearsal()
            st.toast("Full-week rehearsal complete.")

    report = st.session_state.get("g6_launch_report")
    if report:
        st.markdown("##### Go / No-Go")
        _render_launch_report(report)
    else:
        st.info("Run Launch Check for a live production readiness report.")

    rehearsal = st.session_state.get("g6_rehearsal_report")
    if rehearsal:
        with st.expander("Full-week rehearsal result", expanded=True):
            _render_rehearsal(rehearsal)

    st.markdown("##### Week 1 launch checklist")
    st.markdown(
        """
- **Before Tuesday noon:** launch check has no red items; GitHub automation heartbeat is fresh.
- **Tuesday after noon:** confirm five visible choices at QB/RB/WR/TE/K and make one real lineup on your phone.
- **Sunday before noon:** open Commissioner → Week, refresh NFL data, and scan injury warnings.
- **Sunday 12:00 PM ET:** friends do their final lineup/injury check.
- **Sunday 1:00 PM ET:** verify Sunday automatically becomes the live standings screen.
- **Sunday evening:** confirm scores refresh and roster drill-downs show current game status.
- **Monday 9:00 AM ET:** confirm FINAL results, season points, History, and the champion celebration.
        """
    )

    st.markdown("##### Launch decisions")
    st.caption(
        "Web Push is intentionally deferred for Week 1. The app already works fully without notification permissions/service-worker complexity; "
        "the planned Sunday-noon and Monday-final notifications can be added after the core release is proven in the wild."
    )
