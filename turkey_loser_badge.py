"""Emoji-sized inline rendering for the Turkey Bowl last-place badge.

The 36px transparent PNG is shown at 18 CSS pixels (retina crispness).
Pure presentation: no database reads, scoring, or app-state mutations.
"""
from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path

_BADGE_PATH = Path(__file__).resolve().parent / "assets" / "turkey_bowl_loser_badge_36px.png"
_BADGE_SIZE = 18
_ALT = "Turkey Bowl loser"


@lru_cache(maxsize=1)
def _image_src() -> str:
    return "data:image/png;base64," + base64.b64encode(_BADGE_PATH.read_bytes()).decode("ascii")


def loser_badge_html() -> str:
    try:
        src = _image_src()
    except OSError:
        return " 💩"
    return (
        f'<img src="{src}" alt="{_ALT}" title="{_ALT}" '
        f'width="{_BADGE_SIZE}" height="{_BADGE_SIZE}" '
        f'style="display:inline-block;width:{_BADGE_SIZE}px;height:{_BADGE_SIZE}px;'
        f'min-width:{_BADGE_SIZE}px;max-width:{_BADGE_SIZE}px;'
        'vertical-align:-3px;margin-left:2px;object-fit:contain;" />'
    )


def loser_badge_markdown() -> str:
    try:
        return f"![{_ALT}]({_image_src()})"
    except OSError:
        return "💩"
