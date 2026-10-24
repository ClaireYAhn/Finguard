"""Create demo apps (one per template) and save their keys to backend/.demo_keys.json (git-ignored)."""
from __future__ import annotations

import json
from pathlib import Path

from app.seed import seed_demo_apps

KEYS = Path(__file__).resolve().parent.parent / ".demo_keys.json"


def main() -> None:
    keys = seed_demo_apps()
    KEYS.write_text(json.dumps(keys, indent=2))
    print(f"Seeded {len(keys)} demo apps (FICTIONAL). Keys written to {KEYS} (git-ignored).")
    for k, v in keys.items():
        print(f"  {k:18} {v['app_id']}  {v['key'][:12]}...")


if __name__ == "__main__":
    main()
