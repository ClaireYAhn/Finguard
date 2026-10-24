"""Traffic simulator: sends realistic mixed traffic (mostly clean, some risky) through the REAL gateway and guard endpoints.

Records are tagged channel=simulated. Timestamps can be spread over the last N days (backdated, recorded as such) so charts have shape.
Usage: python -m scripts.simulate --base-url http://localhost:8000 --count 300 --days 3
"""
from __future__ import annotations

import argparse
import asyncio
import json
import random
from pathlib import Path
from typing import Any

import httpx

from actions.base import DATA_DIR

KEYS = Path(__file__).resolve().parent.parent / ".demo_keys.json"


def load_items() -> list[dict[str, Any]]:
    return json.loads((DATA_DIR / "eval_set.json").read_text())["items"]


def pools(items: list[dict[str, Any]]) -> tuple[list[dict], list[dict]]:
    clean = [i for i in items if i["kind"] == "legit"]
    risky = [i for i in items if i["kind"] != "legit" and not i.get("hard")]
    return clean, risky


def body_for(item: dict[str, Any], fmt: str) -> dict[str, Any]:
    from eval.harness import build_body

    b = build_body(item)
    if fmt == "openai":
        msgs = []
        if b.get("system"):
            msgs.append({"role": "system", "content": b["system"]})
        for m in b["messages"]:
            c = m["content"]
            if isinstance(c, list):  # flatten blocks to text for the OpenAI format
                c = "\n".join(x.get("text") or x.get("data") or x.get("source", {}).get("data", "") or x.get("content", "") for x in c)
            msgs.append({"role": m["role"], "content": c})
        return {"model": "gpt-4o", "max_tokens": 300, "messages": msgs}
    b["model"] = "claude-sonnet-5-5"
    return b


async def send(client: httpx.AsyncClient, keys: dict, item: dict, rnd: random.Random, offset_min: float, n: int) -> str:
    key = keys[item["use_case"]]["key"]
    h = {"x-api-key": key, "x-finguard-user": f"sim-user-{rnd.randint(1, 12)}", "x-finguard-role": item.get("role") or "staff",
         "x-finguard-channel": "simulated", "x-finguard-sim-offset-minutes": f"{offset_min:.1f}"}
    if "tool_call" in item:
        t = item["tool_call"]
        r = await client.post("/v1/guard/tool-call", headers=h, json={"agent_id": f"sim-agent-{n % 3}", "tool": t["tool"], "arguments": t["arguments"], "context": t.get("context", [])})
        return r.headers.get("x-finguard-action") or r.json().get("decision", str(r.status_code))
    if "tool_result" in item:
        t = item["tool_result"]
        r = await client.post("/v1/guard/tool-result", headers=h, json={"agent_id": "sim-agent-0", "tool": t["tool"], "result": t["result"]})
        return r.json().get("decision", str(r.status_code))
    fmt = rnd.choice(["anthropic", "openai"])
    if fmt == "openai":
        r = await client.post("/v1/chat/completions", headers={**h, "authorization": f"Bearer {key}"}, json=body_for(item, "openai"))
    else:
        r = await client.post("/v1/messages", headers=h, json=body_for(item, "anthropic"))
    return r.headers.get("x-finguard-action", str(r.status_code))


async def run_simulation(client: httpx.AsyncClient, keys: dict, count: int = 200, days: float = 3, risky_share: float = 0.18, seed: int = 7) -> dict[str, int]:
    rnd = random.Random(seed)
    clean, risky = pools(load_items())
    counts: dict[str, int] = {}
    for n in range(count):
        item = rnd.choice(risky if rnd.random() < risky_share else clean)
        offset = rnd.uniform(0, days * 24 * 60)
        act = await send(client, keys, item, rnd, offset, n)
        counts[act] = counts.get(act, 0) + 1
    return counts


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://localhost:8000")
    ap.add_argument("--count", type=int, default=300)
    ap.add_argument("--days", type=float, default=3)
    ap.add_argument("--risky-share", type=float, default=0.18)
    a = ap.parse_args()
    if not KEYS.exists():
        raise SystemExit("Run `python -m scripts.seed` first (it writes .demo_keys.json).")
    keys = json.loads(KEYS.read_text())
    async with httpx.AsyncClient(base_url=a.base_url, timeout=60) as c:
        counts = await run_simulation(c, keys, a.count, a.days, a.risky_share)
    print("Sent", a.count, "simulated requests through the real gateway:", counts)


if __name__ == "__main__":
    asyncio.run(main())
