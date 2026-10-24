"""Tiny client for the FinGuard agent guard (stdlib only). Call check_call() before EVERY tool execution."""
from __future__ import annotations

import json
import os
import time
import urllib.request
from typing import Any

BASE = os.environ.get("FINGUARD_URL", "http://localhost:8000").rstrip("/")
KEY = os.environ.get("FINGUARD_APP_KEY", "")


def _req(method: str, path: str, body: dict | None = None) -> dict[str, Any]:
    r = urllib.request.Request(BASE + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                               headers={"x-api-key": KEY, "content-type": "application/json"})
    with urllib.request.urlopen(r, timeout=30) as resp:
        return json.loads(resp.read())


def check_call(tool: str, arguments: dict, user: str = "agent-user", role: str = "agent", agent_id: str = "demo-agent", context: list[str] | None = None) -> dict:
    return _req("POST", "/v1/guard/tool-call", {"agent_id": agent_id, "tool": tool, "arguments": arguments, "user": user, "role": role, "context": context or []})


def check_result(tool: str, result: Any, role: str = "agent") -> dict:
    return _req("POST", "/v1/guard/tool-result", {"tool": tool, "result": result, "role": role})


def wait_for_approval(approval_id: str, timeout_s: float = 120, poll_s: float = 2) -> str:
    end = time.time() + timeout_s
    while time.time() < end:
        st = _req("GET", f"/v1/guard/approvals/{approval_id}")["status"]
        if st != "pending":
            return st
        time.sleep(poll_s)
    return "pending"


def guarded(tool: str, fn, arguments: dict, **kw) -> str:
    """Run fn(**arguments) only if FinGuard allows it; returns text for the model."""
    d = check_call(tool, arguments, **kw)
    if d["decision"] == "block":
        return f"[blocked by FinGuard] {d['message']}"
    if d["decision"] == "escalate":
        status = wait_for_approval(d["approval_id"])
        if status != "approved":
            return f"[not executed] human approval {status}"
    if d["decision"] == "modify" and d.get("modified_arguments"):
        arguments = d["modified_arguments"]
    out = str(fn(**arguments))
    r = check_result(tool, out, kw.get("role", "agent"))
    return out if r["decision"] == "allow" else r["message"]
