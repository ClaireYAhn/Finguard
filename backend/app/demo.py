"""Demo runner: the same case with FinGuard off and on, through the real pipeline."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from actions.base import DATA_DIR
from app.db import get_db
from eval.harness import run_item
from eval.metrics import item_violation


def scenarios() -> list[dict[str, Any]]:
    return json.loads((DATA_DIR / "demo_scenarios.json").read_text())["scenarios"]


def _tool_text(item: dict[str, Any], out: dict[str, Any], guardrails: bool) -> str:
    spec = item.get("tool_call") or item.get("tool_result")
    if not guardrails:
        return f"[EXECUTED] {spec['tool']}({json.dumps(spec.get('arguments') or spec.get('result'))[:200]}) ran with no check."
    return out["delivered"] or f"[{out['decision'].upper()}] {spec['tool']}"


async def run_scenario(sc: dict[str, Any]) -> dict[str, Any]:
    sides: dict[str, Any] = {}
    for label, g in (("off", False), ("on", True)):
        out = await run_item(sc, guardrails=g, channel="demo")
        text = _tool_text(sc, out, g) if out["kind"] == "tool" else out["delivered"]
        sides[label] = {"text": text, "action": out["action"], "rules_fired": out["rules_fired"], "trace": out["results"] if g else [], "latency_ms": out["total_ms"],
                        "harmful": bool(item_violation(sc, out)), "audit_id": out["audit_id"], "engine": out["engine"],
                        "model_received": (out["model_input"][-300:] if out["model_input"] else "")}
    payload = {"scenario_id": sc["scenario_id"], "title": sc["title"], "surface": sc["surface"], "use_case": sc["use_case"], "input": sc["input"],
               "without_note": sc["without"], "with_note": sc["with"], "off": sides["off"], "on": sides["on"], "ran_at": datetime.now(UTC).isoformat(timespec="seconds")}
    get_db().execute("INSERT OR REPLACE INTO demo_cache (key,ts,data) VALUES (?,?,?)", [sc["scenario_id"], payload["ran_at"], json.dumps(payload)])
    return payload


def cached() -> list[dict[str, Any]]:
    return [json.loads(r["data"]) for r in get_db().query("SELECT data FROM demo_cache ORDER BY key")]


def scorecard(results: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(results)
    return {"scenarios": n, "harmful_off": sum(r["off"]["harmful"] for r in results), "harmful_on": sum(r["on"]["harmful"] for r in results),
            "stopped_or_fixed": sum(1 for r in results if r["on"]["action"] != "allow"),
            "escalated_to_humans": sum(1 for r in results if r["on"]["action"] == "escalate"),
            "avg_added_latency_ms": round(sum(r["on"]["latency_ms"] - r["off"]["latency_ms"] for r in results) / n, 2) if n else None}
