"""Evaluation runner: every labelled item goes through the real pipeline with FinGuard off and on (isolated in-memory database)."""
from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

import actions  # noqa: F401
from actions.base import DATA_DIR
from app import providers
from app.config import get_settings
from app.db import Database, get_db, use_db
from audit import store as audit
from eval import metrics
from eval.harness import run_item
from policies import store as policies
from registry import store as registry
from registry.templates import TEMPLATES

REQUIRED_FIELDS = ["id", "ts", "app_id", "rule_results", "final_action", "pack", "pack_version", "engine", "prev_hash", "hash", "latency", "channel"]


def load_items() -> list[dict[str, Any]]:
    return json.loads((DATA_DIR / "eval_set.json").read_text())["items"]


async def run_eval(limit: int | None = None, store: bool = True) -> dict[str, Any]:
    items = load_items()[:limit] if limit else load_items()
    started = datetime.now(UTC)
    iso_db = Database(":memory:")
    off: dict[str, dict] = {}
    on: dict[str, dict] = {}
    with use_db(iso_db):
        policies.seed_packs()
        for key in TEMPLATES:
            registry.create_from_template(key, is_demo=True)
        for it in items:  # off first, then on, each item through the real pipeline
            off[it["id"]] = await run_item(it, guardrails=False)
            on[it["id"]] = await run_item(it, guardrails=True)
        rows = iso_db.query("SELECT * FROM audit")
        complete = 0
        ids = {o["audit_id"] for o in on.values() if o["audit_id"]}
        for r in rows:
            if r["id"] in ids and all(r.get(f) not in (None, "") for f in REQUIRED_FIELDS):
                complete += 1
        chain = audit.verify_chain()
        audit_check = {"decisions": len(items), "records_written": len(ids), "complete_records": complete,
                       "complete_share": metrics.rate(complete, len(items)), "chain_ok": chain["ok"], "chain_records": chain["count"]}
    res = metrics.compute(items, off, on, audit_check)
    s = get_settings()
    out = {
        "id": "eval_" + uuid.uuid4().hex[:10], "ts": started.isoformat(timespec="seconds"), "provider": providers.provider_name(),
        "model": "mock-model (deterministic, deliberately risky)" if providers.is_mock() else (s.default_model or "provider default"),
        "mock": providers.is_mock(), "engine": s.engine, "dataset_items": len(items),
        "note": ("These numbers come from the MOCK model. They show how the guardrails behave on a deliberately risky, deterministic model and do not prove performance against a real model."
                 if providers.is_mock() else "Numbers come from the configured real provider; results vary between runs."),
        "results": res,
        "items": [{"id": i["id"], "use_case": i["use_case"], "kind": i["kind"], "expected_action": i["expected_action"], "off_action": off[i["id"]]["action"],
                   "on_action": on[i["id"]]["action"], "off_violation": metrics.item_violation(i, off[i["id"]]) if i["kind"] != "legit" else False,
                   "on_violation": metrics.item_violation(i, on[i["id"]]) if i["kind"] != "legit" else False, "fired": on[i["id"]]["rules_fired"],
                   "input": i["input"][:160], "on_output": on[i["id"]]["delivered"][:200]} for i in items],
    }
    if store:
        get_db().execute("INSERT INTO eval_runs (id,ts,provider,model,results) VALUES (?,?,?,?,?)", [out["id"], out["ts"], out["provider"], out["model"], json.dumps(out)])
    return out


def latest_run() -> dict[str, Any] | None:
    row = get_db().one("SELECT results FROM eval_runs ORDER BY ts DESC LIMIT 1")
    return json.loads(row["results"]) if row else None
