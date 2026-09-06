from __future__ import annotations

from pathlib import Path
import re
import sys

ROOT = Path(__file__).parent

forbidden_literals = [
    re.compile(r"SUPABASE_(?:SERVICE_ROLE_KEY|SECRET_KEY)\s*=\s*['\"](?:ey|sb_secret_)", re.I),
    re.compile(r"COMMISH_PIN\s*=\s*['\"]\d{6}['\"]", re.I),
]

bad = []
for path in ROOT.rglob("*"):
    if not path.is_file() or ".git" in path.parts or "__pycache__" in path.parts or path.name == "release_guard.py":
        continue
    if path.name == "secrets.toml.example":
        continue
    try:
        text = path.read_text("utf-8")
    except Exception:
        continue
    for pat in forbidden_literals:
        if pat.search(text):
            bad.append(str(path.relative_to(ROOT)))

required = [
    ROOT / "app.py",
    ROOT / "auth.py",
    ROOT / "security.py",
    ROOT / "store.py",
    ROOT / "weekly.py",
    ROOT / "weekly_ui.py",
    ROOT / "db/001_gate1_foundation.sql",
    ROOT / "db/002_gate2_weekly_game.sql",
]
missing = [str(p.relative_to(ROOT)) for p in required if not p.exists()]

if bad or missing:
    if bad:
        print("FAIL: possible secret literal in:", ", ".join(bad))
    if missing:
        print("FAIL: missing required files:", ", ".join(missing))
    sys.exit(1)

print("release_guard: PASS")
