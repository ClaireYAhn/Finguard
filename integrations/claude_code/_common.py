"""Shared helpers for the FinGuard Claude Code hooks (stdlib only)."""
from __future__ import annotations

import json
import os
import sys
import urllib.request

BASE = os.environ.get("FINGUARD_URL", "http://localhost:8000").rstrip("/")
KEY = os.environ.get("FINGUARD_APP_KEY", "")
ROLE = os.environ.get("FINGUARD_ROLE", "developer")
FAIL_OPEN = os.environ.get("FINGUARD_FAIL_MODE", "closed") == "open"


def post(path: str, body: dict) -> dict:
    req = urllib.request.Request(BASE + path, method="POST", data=json.dumps(body).encode(),
                                 headers={"x-api-key": KEY, "content-type": "application/json", "x-finguard-channel": "hook",
                                          "x-finguard-user": os.environ.get("USER", "unknown"), "x-finguard-role": ROLE})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def reasons(resp: dict) -> str:
    rs = "; ".join(f"{r['rule_id']} {r['name']}: {r['explanation']}" for r in resp.get("reasons", [])[:3])
    return rs or resp.get("message") or "policy"


def prompt_output(resp: dict) -> dict | None:
    """UserPromptSubmit: the hook cannot rewrite the prompt, so block anything that is not a clean allow."""
    d = resp.get("decision")
    if d == "allow":
        return None
    if d == "modify":
        return {"decision": "block", "reason": f"FinGuard: the prompt contains sensitive data ({reasons(resp)}). Remove it and resubmit."}
    return {"decision": "block", "reason": f"FinGuard blocked this prompt ({d}): {reasons(resp)}"}


def tool_output(resp: dict) -> dict | None:
    d = resp.get("decision")
    if d == "allow":
        return None
    perm = "ask" if d == "escalate" else "deny"
    why = f"FinGuard {d}: {reasons(resp)}" + (f" (review case {resp['approval_id']})" if resp.get("approval_id") else "")
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": perm, "permissionDecisionReason": why}}


def error_output(event: str, exc: Exception) -> dict | None:
    if FAIL_OPEN:
        return None
    msg = f"FinGuard is unreachable ({exc}); failing closed."
    if event == "UserPromptSubmit":
        return {"decision": "block", "reason": msg}
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": msg}}


def emit(out: dict | None) -> None:
    if out:
        sys.stdout.write(json.dumps(out))
    sys.exit(0)
