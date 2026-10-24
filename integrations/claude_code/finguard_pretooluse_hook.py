#!/usr/bin/env python3
"""Claude Code PreToolUse hook: asks the FinGuard agent guard before every tool call."""
import json
import sys

from _common import emit, error_output, post, tool_output

if __name__ == "__main__":
    data = json.load(sys.stdin)  # fields per Claude Code docs: tool_name, tool_input, tool_use_id, ...
    try:
        emit(tool_output(post("/v1/guard/tool-call", {"agent_id": "claude-code", "tool": data.get("tool_name", ""), "arguments": data.get("tool_input", {})})))
    except Exception as exc:  # noqa: BLE001
        emit(error_output("PreToolUse", exc))
