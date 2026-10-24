"""Printable compliance evidence report (HTML that prints to PDF). All numbers come from the audit log."""
from __future__ import annotations

import html
import json
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from app.db import get_db
from audit import store as audit
from registry import store as registry

LIMITS = [
    "FinGuard only sees traffic that is routed through it (gateway, agent guard, hooks). It cannot see public consumer apps such as the claude.ai website.",
    "Pattern and classifier checks miss some cases; a clean record is not proof that nothing risky happened.",
    "Streaming responses are buffered so output can be checked before release; this adds latency.",
    "Regulation mappings are illustrative, not legal advice. Guardrails reduce risk and create evidence but do not guarantee compliance; humans stay accountable.",
    "The hash chain demonstrates tamper evidence; it is not a certified immutable store. Removing the newest records is only detectable if the head hash was recorded elsewhere.",
]


def e(x: Any) -> str:
    return html.escape(str(x))


def render_report(app_id: str, date_from: str | None, date_to: str | None) -> str | None:
    app = registry.get_app(app_id)
    if not app:
        return None
    rows = audit.query_records(app_id=app_id, date_from=date_from, date_to=date_to, limit=100000)
    rows = [r for r in rows if r["channel"] != "review"]
    acts = Counter(r["final_action"] for r in rows)
    fired: Counter = Counter()
    names: dict[str, str] = {}
    regs: dict[str, set[str]] = {}
    for r in rows:
        for x in r["rule_results"]:
            if x["status"] != "pass":
                fired[x["rule_id"]] += 1
                names[x["rule_id"]] = x["name"]
                regs.setdefault(x["rule_id"], set()).update(g["ref"] for g in x.get("regulations", []))
    versions = Counter(f"{r['pack']}@v{r['pack_version']}" for r in rows)
    channels = Counter(r["channel"] for r in rows)
    sim = channels.get("simulated", 0)
    cases = [c for c in audit.list_cases(app_id=app_id) if (not date_from or c["created_at"][:10] >= date_from) and (not date_to or c["created_at"][:10] <= date_to)]
    chain = audit.verify_chain()
    now = datetime.now(UTC).isoformat(timespec="seconds")
    rng = f"{date_from or 'start'} to {date_to or 'now'}"
    tr = lambda cells, th=False: "<tr>" + "".join(f"<{'th' if th else 'td'}>{c}</{'th' if th else 'td'}>" for c in cells) + "</tr>"  # noqa: E731
    parts = [f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>FinGuard evidence report - {e(app['name'])}</title>
<style>body{{font:14px/1.5 system-ui,sans-serif;max-width:900px;margin:24px auto;padding:0 16px;color:#10223d}}h1{{color:#0b2545}}h2{{border-bottom:2px solid #0b2545;padding-bottom:4px;margin-top:28px}}
table{{border-collapse:collapse;width:100%;margin:8px 0}}td,th{{border:1px solid #c9d3e0;padding:6px 8px;text-align:left;vertical-align:top}}th{{background:#eef2f8}}
.banner{{background:#fff4d6;border:1px solid #e0b100;padding:8px 12px;border-radius:6px}}.ok{{color:#0a7a3d;font-weight:600}}.bad{{color:#b3261e;font-weight:600}}
@media print{{.noprint{{display:none}}body{{margin:0}}}}</style></head><body>
<p class="banner"><strong>Demo data is fictional. Not financial, legal or regulatory advice.</strong></p>
<button class="noprint" onclick="window.print()">Print / save as PDF</button>
<h1>Compliance evidence report</h1>
<p><strong>{e(app['name'])}</strong> &middot; owner {e(app['owner'] or 'n/a')} &middot; risk tier {e(app['risk_tier'])} &middot; pack {e(app['policy_pack'])}<br>
Period: {e(rng)} &middot; generated {e(now)}</p>
<p>{e(app['eu_ai_act_note'])}</p>"""]
    if sim:
        parts.append(f'<p class="banner">{sim} of {len(rows)} records in this period are <strong>simulated</strong> traffic (channel=simulated), generated for demonstration.</p>')
    parts.append(f"<h2>1. Volume and actions</h2><p>{len(rows)} governed request(s).</p><table>{tr(['Action', 'Count'], True)}")
    for a in ("allow", "modify", "block", "escalate", "error"):
        parts.append(tr([a, acts.get(a, 0)]))
    parts.append("</table>" + "<p>Channels: " + e(", ".join(f"{k}: {v}" for k, v in channels.items()) or "none") + "</p>")
    parts.append(f"<h2>2. Rules fired</h2><table>{tr(['Rule', 'Name', 'Times fired', 'Regulation references (illustrative)'], True)}")
    for rid, n in fired.most_common():
        parts.append(tr([e(rid), e(names[rid]), n, e("; ".join(sorted(regs.get(rid, []))))]))
    if not fired:
        parts.append(tr(["-", "No rules fired in this period", 0, ""]))
    parts.append("</table>")
    parts.append(f"<h2>3. Escalations and decisions</h2><table>{tr(['Case', 'Kind', 'Created', 'Status', 'Reviewer note'], True)}")
    for c in cases:
        parts.append(tr([e(c["id"]), e(c["kind"]), e(c["created_at"][:16]), e(c["status"]), e(c.get("reviewer_note") or "")]))
    if not cases:
        parts.append(tr(["-", "No cases in this period", "", "", ""]))
    decisions = [r for r in audit.query_records(app_id=app_id, channel="review", date_from=date_from, date_to=date_to, limit=1000)]
    parts.append(f"</table><p>{len(decisions)} review decision(s) recorded as chained audit records.</p>")
    cls = "ok" if chain["ok"] else "bad"
    parts.append(f'<h2>4. Audit chain verification</h2><p class="{cls}">{e(chain["message"])}</p><p>Head hash (store this externally to detect removal of newest records): <code>{e(chain["head_hash"])}</code></p>')
    parts.append(f"<h2>5. Policy versions in force</h2><table>{tr(['Pack version used', 'Requests'], True)}")
    for v, n in versions.most_common():
        parts.append(tr([e(v), n]))
    parts.append("</table>")
    parts.append("<h2>6. Limitations</h2><ul>" + "".join(f"<li>{e(x)}</li>" for x in LIMITS) + "</ul>")
    parts.append("</body></html>")
    _ = get_db, json
    return "".join(parts)
