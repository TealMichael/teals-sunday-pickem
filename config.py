from __future__ import annotations

APP_NAME = "Teal's Sunday Pick'em"
APP_TAGLINE = "Pick five. Own Sunday."
APP_VERSION = "0.2.5"
TIMEZONE_NAME = "America/New_York"

PLAYER_PIN_LENGTH = 4
COMMISH_PIN_LENGTH = 6
MAX_NICKNAME_LENGTH = 15
REMEMBER_DAYS = 210  # comfortably covers an NFL season
COOKIE_NAME = "tsp_session_v1"
REMEMBER_STORAGE_KEY = "tsp_remember_device_v1"
REMEMBER_COOKIE_MAX_AGE = REMEMBER_DAYS * 24 * 60 * 60

# Low-entropy 4-digit PINs require both slow hashing and login throttling.
PBKDF2_ITERATIONS = 600_000
LOGIN_WINDOW_MINUTES = 10
MAX_FAILED_LOGINS_PER_WINDOW = 8
