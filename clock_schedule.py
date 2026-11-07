"""Validated, persistent AWTRIX broadcast slot configuration.

Only the Sunday live phase may reveal current-week Pick'em information.
These constants are shared by the Commissioner editor and the server store;
the database migration enforces the same phase-specific allowlists.
"""

from __future__ import annotations

from typing import Sequence


CATEGORY_LABELS = {
    "preview": "NFL Sunday Preview",
    "manual": "Commissioner Message",
    "readiness": "Lineup Readiness",
    "season": "Season Standings",
    "caleb": "Caleb 4K Watch",
    "off": "Off (no message)",
    "live_games": "NFL Live Scores",
    "weekly": "Weekly Standings",
    "player": "Player Update",
    "pulse": "Pick'em Pulse",
}

SAFE_PRELOCK = ("preview", "manual", "readiness", "season", "caleb", "off")
LIVE_CATEGORIES = (
    "live_games", "weekly", "player", "season", "pulse",
    "caleb", "manual", "preview", "off",
)

PHASES = {
    "saturday": {
        "label": "Saturday Preview",
        "column": "saturday_slots",
        "minutes": 15,
        "allowed": SAFE_PRELOCK,
        "description": "All Saturday, every 15 minutes",
    },
    "pregame": {
        "label": "Sunday Pregame",
        "column": "pregame_slots",
        "minutes": 5,
        "allowed": SAFE_PRELOCK,
        "description": "Sunday 10:30 AM–1:00 PM, every 5 minutes",
    },
    "live": {
        "label": "Sunday Live",
        "column": "live_slots",
        "minutes": 5,
        "allowed": LIVE_CATEGORIES,
        "description": "Sunday 1:00 PM–midnight, every 5 minutes",
    },
}

# v1.0.17 remains the initial behavior, including Week 1's season-to-Pulse
# fallback (handled inside clock_feed, not by this configuration).
DEFAULT_SLOTS = {
    "saturday": ("preview",) * 4,
    "pregame": ("preview", "manual", "readiness", "season") * 3,
    "live": (
        "live_games", "weekly", "player", "live_games",
        "weekly", "season", "live_games", "weekly",
        "caleb", "live_games", "weekly", "manual",
    ),
}


def validate_slots(phase: str, slots: Sequence[str]) -> list[str]:
    """Reject malformed, unsupported or pre-lock-private configurations."""
    if phase not in PHASES:
        raise ValueError("Unknown ticker schedule phase.")
    expected = 60 // int(PHASES[phase]["minutes"])
    if not isinstance(slots, (list, tuple)) or len(slots) != expected:
        raise ValueError(f"{PHASES[phase]['label']} needs exactly {expected} slots.")
    allowed = PHASES[phase]["allowed"]
    if any(not isinstance(value, str) or value not in allowed for value in slots):
        raise ValueError("This schedule includes a category that is not allowed before lock or in this phase.")
    return list(slots)


def slot_label(phase: str, index: int) -> str:
    """Local minutes-past-the-hour label used consistently in the editor."""
    minutes = int(PHASES[phase]["minutes"])
    return f":{index * minutes:02d}"
