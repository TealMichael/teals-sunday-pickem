"""Turkey Bowl's isolated worker. GitHub holiday workflow uses existing secrets."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from store import SupabaseStore
from turkey_bowl import run_auto

if __name__ == "__main__":
    url = os.getenv("SUPABASE_URL", "").strip()
    key = (os.getenv("SUPABASE_SECRET_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    if not url or not key:
        raise SystemExit("Missing existing Supabase repository secrets.")
    print(run_auto(SupabaseStore(url, key)))
