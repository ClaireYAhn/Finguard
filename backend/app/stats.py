"""Overview statistics computed from real audit records only."""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from app.db import get_db
from policies import store as policies

COUNTED = "channel NOT IN ('review')"


def _since(days: int) -> str:
    return (datetime.now(UTC) - timedelta(days=days)).isoformat(timespec="seconds")


def _rows(since: str) -> list[dict[str, Any]]:
    rows = get_db().query(f"SELECT ts, app_id, app_name, channel, final_action, rule_results, role FROM audit WHERE {COUNTED} AND ts >= ? ORDER BY ts", [since])
    for r in rows:
        try:
            r["rules"] = json.loads(r["rule_results"] or "[]")
        except json.JSONDecodeError:
            r["rules"] = []
    return rows


def app_activity(days: int = 7) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = defaultdict(lambda: {"requests": 0, "blocked": 0, "modified": 0, "escalated": 0, "last_activity": None})
    for r in get_db().query(f"SELECT app_id, final_action, ts FROM audit WHERE {COUNTED} AND ts >= ?", [_since(days)]):
        a = out[r["app_id"]]
        a["requests"] += 1
        a["blocked"] += r["final_action"] == "block"
        a["modified"] += r["final_action"] == "modify"
        a["escalated"] += r["final_action"] == "escalate"
    for r in get_db().query(f"SELECT app_id, MAX(ts) AS last FROM audit WHERE {COUNTED} GROUP BY app_id"):
        out[r["app_id"]]["last_activity"] = r["last"]
    return out


def overview(days: int = 14) -> dict[str, Any]:
    rows = _rows(_since(days))
    apps = {a["id"]: a for a in get_db().query("SELECT id, name, risk_tier, enabled, policy_pack FROM apps")}
    acts = Counter(r["final_action"] for r in rows)
    open_reviews = get_db().one("SELECT COUNT(*) AS n FROM reviews WHERE status='open'")["n"]  # type: ignore[index]
    week = app_activity(7)
    live = [a for a in apps.values() if a["enabled"]]
    idle = [a for a in live if week.get(a["id"], {}).get("requests", 0) == 0]

    hourly = days <= 2
    buckets: dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        key = r["ts"][:13] + ":00" if hourly else r["ts"][:10]
        buckets[key][r["final_action"]] += 1
    series = [{"t": k, "allow": v["allow"], "modify": v["modify"], "block": v["block"], "escalate": v["escalate"], "total": sum(v.values())} for k, v in sorted(buckets.items())]

    per_app: dict[str, dict[str, Any]] = {}
    per_rule: dict[str, dict[str, Any]] = {}
    for r in rows:
        a = per_app.setdefault(r["app_id"], {"app_id": r["app_id"], "app": r["app_name"], "tier": apps.get(r["app_id"], {}).get("risk_tier", "?"), "requests": 0, "blocked": 0, "modified": 0, "escalated": 0})
        a["requests"] += 1
        a["blocked"] += r["final_action"] == "block"
        a["modified"] += r["final_action"] == "modify"
        a["escalated"] += r["final_action"] == "escalate"
        for x in r["rules"]:
            if x["status"] != "pass":
                pr = per_rule.setdefault(x["rule_id"], {"rule_id": x["rule_id"], "name": x["name"], "fired": 0, "modified": 0, "blocked": 0, "escalated": 0})
                pr["fired"] += 1
                pr[x["status"]] += 1
    for a in per_app.values():
        a["violation_rate"] = round((a["blocked"] + a["modified"] + a["escalated"]) / a["requests"], 4) if a["requests"] else 0
    top_rules = sorted(per_rule.values(), key=lambda x: -x["fired"])

    # attention list
    attention: list[dict[str, Any]] = []
    prev = {}
    for r in get_db().query(f"SELECT app_id, COUNT(*) AS n FROM audit WHERE {COUNTED} AND final_action='block' AND ts >= ? AND ts < ? GROUP BY app_id", [_since(14), _since(7)]):
        prev[r["app_id"]] = r["n"]
    for aid, a in week.items():
        if aid in apps and a["blocked"] >= 3 and a["blocked"] > prev.get(aid, 0) * 1.5:
            attention.append({"kind": "rising_blocks", "app_id": aid, "app": apps[aid]["name"], "detail": f"{a['blocked']} blocks in the last 7 days vs {prev.get(aid, 0)} in the 7 days before."})
    for r in get_db().query("SELECT app_id, app_name, COUNT(*) AS n, MIN(created_at) AS oldest FROM reviews WHERE status='open' GROUP BY app_id, app_name"):
        attention.append({"kind": "unreviewed_escalations", "app_id": r["app_id"], "app": r["app_name"], "detail": f"{r['n']} open review case(s); oldest {r['oldest'][:16].replace('T', ' ')}."})
    for a in apps.values():
        if a["risk_tier"] == "high" and a["enabled"]:
            cur, first = policies.get_pack(a["policy_pack"]), policies.get_pack(a["policy_pack"], 1)
            if cur and first:
                was = {x["id"] for x in first["rules"] if x["enabled"]}
                off = [x["id"] for x in cur["rules"] if not x["enabled"] and x["id"] in was]
                if off:
                    attention.append({"kind": "disabled_rules", "app_id": a["id"], "app": a["name"], "detail": f"High-risk app has rule(s) switched off since v1: {', '.join(off)}."})
    for a in idle:
        attention.append({"kind": "no_activity", "app_id": a["id"], "app": a["name"], "detail": "Enabled but no requests in the last 7 days."})

    sim = sum(1 for r in rows if r["channel"] == "simulated")
    return {
        "days": days,
        "cards": {"requests": len(rows), "blocked": acts["block"], "modified": acts["modify"], "escalated": acts["escalate"], "allowed": acts["allow"],
                  "open_reviews": open_reviews, "apps_live": len(live), "apps_idle": len(idle), "apps_total": len(apps)},
        "series": series, "bucket": "hour" if hourly else "day",
        "per_app": sorted(per_app.values(), key=lambda x: -x["requests"]), "per_rule": top_rules, "top_rules": top_rules[:8],
        "heatmap": [{"app": a["app"], "tier": a["tier"], "requests": a["requests"], "violation_rate": a["violation_rate"]} for a in per_app.values()],
        "attention": attention, "simulated_requests": sim,
        "simulated_share": round(sim / len(rows), 4) if rows else 0,
        "channels": dict(Counter(r["channel"] for r in rows)),
    }
