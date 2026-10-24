"""Run the full evaluation (FinGuard off vs on) through the real pipeline and optionally write docs/evaluation-report.md."""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from app.db import get_db
from eval.report import render
from eval.runner import run_eval
from policies import store as policies

DOCS = Path(__file__).resolve().parent.parent.parent / "docs"


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write-report", action="store_true", help="write docs/evaluation-report.md and docs/evaluation-results.json")
    ap.add_argument("--json", action="store_true", help="print the full run as JSON")
    a = ap.parse_args()
    get_db()
    policies.seed_packs()
    run = await run_eval()
    o = run["results"]["overall"]
    print(f"Model: {run['model']} | items: {run['dataset_items']} | violations off {o['violation_rate_off']} -> on {o['violation_rate_on']} | FP on {o['false_positive_rate_on']} | "
          f"expected-action match {o['expected_action_match']} | audit complete {run['results']['audit']['complete_share']}")
    if a.write_report:
        DOCS.mkdir(exist_ok=True)
        (DOCS / "evaluation-report.md").write_text(render(run))
        (DOCS / "evaluation-results.json").write_text(json.dumps(run, indent=1))
        print("wrote docs/evaluation-report.md and docs/evaluation-results.json")
    if a.json:
        print(json.dumps(run, indent=1))


if __name__ == "__main__":
    asyncio.run(main())
