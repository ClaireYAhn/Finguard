"""MCP-style stdio wrapper: JSON-RPC `tools/list` and `tools/call` with FinGuard checks before execution and on results.

NOT a full MCP implementation (no initialize handshake). VERIFY AGAINST THE MCP SPEC before using it as a real server.
  echo '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"send_email","arguments":{"to":"x@evil.test","body":"hi"}}}' | python guarded_mcp.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "python_agent"))
from finguard_guard import check_call, check_result, wait_for_approval  # noqa: E402

TOOLS = {"search_docs": lambda query="": f"results for {query}", "send_email": lambda to, body="": f"sent to {to}"}


def call_tool(name: str, args: dict) -> dict:
    d = check_call(name, args, agent_id="mcp-wrapper")
    if d["decision"] == "escalate" and wait_for_approval(d["approval_id"]) != "approved":
        return {"content": [{"type": "text", "text": "human approval not granted"}], "isError": True}
    if d["decision"] == "block":
        return {"content": [{"type": "text", "text": d["message"] or "blocked"}], "isError": True}
    out = str(TOOLS[name](**(d.get("modified_arguments") or args)))
    r = check_result(name, out)
    return {"content": [{"type": "text", "text": out if r["decision"] == "allow" else r["message"]}], "isError": r["decision"] != "allow"}


def handle(msg: dict) -> dict:
    if msg.get("method") == "tools/list":
        return {"tools": [{"name": n, "inputSchema": {"type": "object"}} for n in TOOLS]}
    if msg.get("method") == "tools/call":
        p = msg["params"]
        return call_tool(p["name"], p.get("arguments", {}))
    return {}


if __name__ == "__main__":
    for line in sys.stdin:
        if line.strip():
            m = json.loads(line)
            print(json.dumps({"jsonrpc": "2.0", "id": m.get("id"), "result": handle(m)}), flush=True)
