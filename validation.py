from __future__ import annotations

import re
import unicodedata

from config import MAX_NICKNAME_LENGTH, PLAYER_PIN_LENGTH


_NICKNAME_ALLOWED = re.compile(r"^[A-Za-z0-9 _.'-]+$")


def normalize_nickname(value: str) -> str:
    value = unicodedata.normalize("NFKC", str(value or ""))
    value = " ".join(value.strip().split())
    return value


def nickname_key(value: str) -> str:
    return normalize_nickname(value).casefold()


def validate_nickname(value: str) -> tuple[bool, str]:
    clean = normalize_nickname(value)
    if not clean:
        return False, "Choose a nickname."
    if len(clean) > MAX_NICKNAME_LENGTH:
        return False, f"Keep your nickname to {MAX_NICKNAME_LENGTH} characters or fewer."
    if not _NICKNAME_ALLOWED.fullmatch(clean):
        return False, "Use letters, numbers, spaces, apostrophes, periods, hyphens, or underscores."
    return True, ""


def validate_player_pin(pin: str) -> tuple[bool, str]:
    pin = str(pin or "")
    if not (pin.isdigit() and len(pin) == PLAYER_PIN_LENGTH):
        return False, f"Your PIN must be exactly {PLAYER_PIN_LENGTH} digits."
    return True, ""


def _looks_emoji_codepoint(cp: int) -> bool:
    return (
        0x1F1E6 <= cp <= 0x1F1FF  # flags
        or 0x1F300 <= cp <= 0x1FAFF
        or 0x2600 <= cp <= 0x27BF
        or 0x2300 <= cp <= 0x23FF
        or cp in {0x00A9, 0x00AE, 0x203C, 0x2049, 0x2122, 0x2139, 0x3030, 0x303D, 0x3297, 0x3299}
    )


def validate_single_emoji(value: str) -> tuple[bool, str]:
    # Accept one Unicode emoji grapheme, including flags, skin tones and ZWJ families.
    # Reject plain text and two independent emoji. This avoids a runtime emoji package.
    value = str(value or "").strip()
    if not value:
        return False, "Pick one emoji."

    cps = [ord(ch) for ch in value]
    joiner = 0x200D
    variation = {0xFE0E, 0xFE0F}
    skin = set(range(0x1F3FB, 0x1F400))
    combining_keycap = 0x20E3

    # Keycap emoji such as 1️⃣.
    if cps[-1:] == [combining_keycap] and chr(cps[0]) in "#*0123456789":
        return True, ""

    bases = [cp for cp in cps if cp not in variation and cp not in skin and cp != joiner]
    if not bases:
        return False, "Choose one emoji only."

    # Flag emoji is exactly two regional indicator symbols.
    if len(bases) == 2 and all(0x1F1E6 <= cp <= 0x1F1FF for cp in bases):
        return True, ""

    # ZWJ sequences are one visible emoji when every segment contains an emoji base.
    if joiner in cps:
        segments = value.split(chr(joiner))
        if segments and all(any(_looks_emoji_codepoint(ord(ch)) for ch in seg) for seg in segments):
            return True, ""
        return False, "Choose one emoji only."

    emoji_bases = [cp for cp in bases if _looks_emoji_codepoint(cp)]
    if len(emoji_bases) == 1 and len(bases) == 1:
        return True, ""

    return False, "Choose one emoji only."
