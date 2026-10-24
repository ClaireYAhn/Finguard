from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "integrations" / "claude_code"))
import _common as h  # noqa: E402


def test_prompt_hook_outputs():
    assert h.prompt_output({"decision": "allow"}) is None
    assert h.prompt_output({"decision": "block", "reasons": [{"rule_id": "IN-02", "name": "x", "explanation": "y"}]})["decision"] == "block"
    assert "Remove it" in h.prompt_output({"decision": "modify", "reasons": []})["reason"]


def test_pretooluse_hook_outputs():
    assert h.tool_output({"decision": "allow"}) is None
    o = h.tool_output({"decision": "block", "reasons": []})["hookSpecificOutput"]
    assert o["hookEventName"] == "PreToolUse" and o["permissionDecision"] == "deny"
    assert h.tool_output({"decision": "escalate", "approval_id": "case_1", "reasons": []})["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_fail_closed_default():
    assert h.error_output("PreToolUse", RuntimeError("down"))["hookSpecificOutput"]["permissionDecision"] == "deny"
