"""Each seeded use case end to end in mock mode, driven by the labelled evaluation set (non-hard chat items) over the real HTTP gateway."""
from __future__ import annotations

import json

import pytest

from actions.base import DATA_DIR
from eval.harness import build_body

ITEMS = [i for i in json.loads((DATA_DIR / "eval_set.json").read_text())["items"] if "tool_call" not in i and "tool_result" not in i and not i.get("hard")]


@pytest.mark.parametrize("item", ITEMS, ids=[i["id"] for i in ITEMS])
def test_expected_action_over_gateway(client, item):
    app = client.apps[item["use_case"]]
    role = item.get("role") or app["app"]["default_role"]
    body = build_body(item)
    body["model"] = "claude-sonnet-5-5"
    r = client.post("/v1/messages", headers={"x-api-key": app["key"], "x-finguard-role": role}, json=body)
    assert r.status_code == 200
    assert r.headers["x-finguard-action"] == item["expected_action"], (item["input"][:80], r.headers["x-finguard-rules"])
    fired = set(filter(None, r.headers["x-finguard-rules"].split(",")))
    assert set(item["expected_categories"]) <= fired, (fired, item["expected_categories"])
