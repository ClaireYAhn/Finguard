"""Agent guard: decide allow / modify / block / escalate for a tool call or a tool result."""
from __future__ import annotations

import json
import time
from typing import Any

from actions.base import Ctx, Segment
from audit import store as audit
from policies import store as policies

from .config import get_settings
from .engines import get_engine
from .pipeline import _dump, _fired


async def guard_tool(*, app: dict[str, Any], kind: str, tool: str, args: dict[str, Any] | None, result_text: str | None, agent_id: str, user: str,
                     role: str, context: list[str] | None, channel: str = "tool-call", engine_name: str | None = None) -> dict[str, Any]:
    """kind = 'call' (TL-* rules) or 'result' (TR-* rules)."""
    t0 = time.perf_counter()
    pack = policies.get_pack(app["policy_pack"]) or policies.get_pack("general_agent")
    assert pack is not None
    prefix = "TL-" if kind == "call" else "TR-"
    rules = [r for r in policies.rule_configs(pack) if r.stage == "tool" and r.id.startswith(prefix)]
    segs = [Segment("user", c, i) for i, c in enumerate(context or [])]
    text = result_text if kind == "result" else json.dumps(args or {})
    ctx = Ctx(text=text or "", segments=segs, user_input=text or "", role=role, app=app, settings=pack.get("settings", {}), tool_name=tool, tool_args=args or {})
    out = await get_engine(engine_name or get_settings().engine).run("tool", ctx, rules)
    results = _dump(out.results)
    decision = out.action
    modified_args = None
    if decision == "modify" and kind == "call":
        for r in out.results:
            if r.status == "modified" and r.new_text:
                modified_args = json.loads(r.new_text)
    latency = {"tool_ms": round((time.perf_counter() - t0) * 1000, 3)}
    shown = json.dumps(args or {}) if kind == "call" else (result_text or "")
    label = f"tool_{kind}:{tool}"
    rec = audit.write_audit(app_id=app["id"], app_name=app["name"], user=user, role=role, channel=channel, original_input=f"{label} {shown}"[:4000],
                            redacted_input=f"{label} {json.dumps(modified_args) if modified_args else ''}"[:4000], raw_output=None,
                            final_output=out.safe_message if decision in ("block", "escalate") else None, rule_results=results, final_action=decision,
                            latency=latency, pack=pack["pack"], pack_version=pack["version"], model="", engine=out.engine,
                            extra={"agent_id": agent_id, "tool": tool, "kind": kind, "engine_note": out.engine_note})
    approval_id = None
    if decision == "escalate" or (out.open_case and decision != "block"):
        case = audit.create_case(audit_id=rec["id"], app_id=app["id"], app_name=app["name"], kind="tool_approval" if kind == "call" else "tool_result",
                                 reason=f"Agent '{agent_id}' wants to run '{tool}'", rule_ids=_fired(results),
                                 payload={"agent_id": agent_id, "tool": tool, "arguments": json.loads(audit.storage_redact(json.dumps(args or {})) or "{}") if kind == "call" else {}, "user": user, "role": role})
        approval_id = case["id"]
        decision = "escalate"
    return {"decision": decision, "request_id": rec["id"], "approval_id": approval_id, "modified_arguments": modified_args,
            "reasons": [{"rule_id": r["rule_id"], "name": r["name"], "status": r["status"], "explanation": r["explanation"], "evidence": r["evidence"],
                         "regulations": [x["ref"] for x in r["regulations"]]} for r in results if r["status"] != "pass"],
            "message": out.safe_message if decision in ("block", "escalate") else None, "engine": out.engine, "pack_version": pack["version"], "trace": results}
