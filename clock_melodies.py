"""Optional Commissioner-only AWTRIX melodies.

Stored in a separate per-week table so the original Sunday Clock settings,
clock snapshot generation, and NFL/scoring paths remain untouched.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

# These IDs are the entire allowed set; the SQL feed wrapper owns the actual
# static RTTTL notes. Neither the browser nor the clock can submit custom sound.
MELODY_CHOICES = {
    "happy_birthday": "Happy Birthday",
    "jingle_bells": "Jingle Bells",
    "twinkle_twinkle": "Twinkle Twinkle Little Star",
    "ode_to_joy": "Ode to Joy",
    "celebration_chime": "Celebration Chime",
}
MELODY_TARGETS = {
    "welcome": "Welcome / Who's Here",
    "party": "Food or Party Message",
    "custom": "Custom Message",
}


def get_week_melody(store: Any, week_id: str) -> dict[str, Any] | None:
    """Return default-OFF settings; None means the optional SQL isn't ready.

    An unavailable music table must never prevent saving ordinary text messages.
    """
    defaults: dict[str, Any] = {
        "week_id": str(week_id),
        "enabled": False,
        "target": "welcome",
        "tune": "happy_birthday",
    }
    try:
        result = (
            store._table("clock_message_melodies")
            .select("week_id,enabled,target,tune")
            .eq("week_id", str(week_id))
            .limit(1)
            .execute()
        )
    except Exception:
        return None
    if result.data:
        row = result.data[0]
        if isinstance(row, dict):
            defaults.update(row)
    # Never expose unexpected database values as options in the form.
    if defaults["target"] not in MELODY_TARGETS:
        defaults["target"] = "welcome"
    if defaults["tune"] not in MELODY_CHOICES:
        defaults["tune"] = "happy_birthday"
    return defaults


def save_week_melody(
    store: Any, week_id: str, *, enabled: bool, target: str, tune: str
) -> dict[str, Any]:
    """Write only the isolated optional melody row, never clock_week_settings."""
    if target not in MELODY_TARGETS or tune not in MELODY_CHOICES:
        raise ValueError("Choose one of the available message and melody options.")
    payload = {
        "week_id": str(week_id),
        "enabled": bool(enabled),
        "target": target,
        "tune": tune,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    result = store._table("clock_message_melodies").upsert(payload, on_conflict="week_id").execute()
    if not result.data:
        raise RuntimeError("The melody choice was not confirmed by the database.")
    return result.data[0]
