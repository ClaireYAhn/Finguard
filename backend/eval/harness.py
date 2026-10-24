"""Run one labelled item through the real pipeline with FinGuard off or on."""
from __future__ import annotations

import time
from typing import Any

from app.pipeline import govern
from app.toolguard import guard_tool
from gateway.adapters import parse_anthropic
from registry import store as registry


def build_body(item: dict[str, Any]) -> dict[str, Any]:
    msgs: list[dict[str, Any]] = [dict(m) for m in item.get("history", [])]
    content: list[dict[str, Any]] = [{"type": "text", "text": item["input"]}]
    for blk in item.get("blocks", []):
        if blk["type"] == "document":
            content.append({"type": "document", "source": {"type": "text", "media_type": "text/plain", "data": blk["text"]}})
        else:
            content.append({"type": "tool_result", "tool_use_id": "toolu_eval", "content": blk["text"]})
    msgs.append({"role": "user", "content": content if item.get("blocks") else item["input"]})
    body: dict[str, Any] = {"model": "", "max_tokens": 512, "messages": msgs}
    if item.get("system"):
        body["system"] = item["system"]
    return body


async def run_item(item: dict[str, Any], guardrails: bool, channel: str = "eval") -> dict[str, Any]:
    app = registry.get_by_template(item["use_case"])
    assert app, f"no app for template {item['use_case']}"
    role = item.get("role") or app["default_role"]
    t0 = time.perf_counter()
    if "tool_call" in item or "tool_result" in item:
        is_call = "tool_call" in item
        spec = item["tool_call"] if is_call else item["tool_result"]
        if not guardrails:
            return {"delivered": "", "model_input": "", "action": "allow", "decision": "allow", "rules_fired": [], "results": [], "total_ms": round((time.perf_counter() - t0) * 1000, 3),
                    "audit_id": None, "engine": "off", "modified_args": None, "kind": "tool"}
        r = await guard_tool(app=app, kind="call" if is_call else "result", tool=spec["tool"], args=spec.get("arguments"), result_text=spec.get("result"),
                             agent_id="eval-agent", user="eval", role=role, context=spec.get("context"), channel=channel)
        return {"delivered": r["message"] or "", "model_input": "", "action": r["decision"], "decision": r["decision"], "rules_fired": [x["rule_id"] for x in r["reasons"]],
                "results": r["trace"], "total_ms": round((time.perf_counter() - t0) * 1000, 3), "audit_id": r["request_id"], "engine": r["engine"],
                "modified_args": r["modified_arguments"], "kind": "tool"}
    conv = parse_anthropic(build_body(item))
    res = await govern(app=app, conv=conv, role=role, user="eval", channel=channel, guardrails=guardrails)
    return {"delivered": res.final_text, "model_input": res.model_input, "action": res.action if guardrails else "allow", "decision": None, "rules_fired": res.rules_fired,
            "results": res.results, "total_ms": round((time.perf_counter() - t0) * 1000, 3), "audit_id": res.audit_id, "engine": res.engine, "modified_args": None, "kind": "chat",
            "model_called": res.model_called}
