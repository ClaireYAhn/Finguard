"""Agent tool-call and tool-result checks (TL-01..TL-06, TR-01, TR-02)."""
from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlparse

from . import dataref
from .base import Ctx, RuleConfig, Segment, make_result, register, violation_status
from .input_checks import DOC_ID_RE, in04, scan_injection
from .pii import find_pii, redact

OUTBOUND_RE = re.compile(r"(email|mail|smtp|http|fetch|request|webhook|upload|post|send|slack|teams|sftp|ftp|share|publish|notify)", re.I)
HIGH_IMPACT_RE = re.compile(r"(pay|payment|transfer|wire|send_money|refund|close_account|delete_account|update_account|change_(?:address|beneficiary|limit|password)|approve_(?:loan|credit)|execute_order|place_order|trade|withdraw)", re.I)
BULK_NAME_RE = re.compile(r"(export|dump|download_all|bulk|extract_all|list_all|backup)", re.I)
DEST_KEYS = {"to", "cc", "bcc", "recipient", "recipients", "url", "endpoint", "destination", "host", "webhook", "webhook_url", "address", "email", "target"}


def flatten(obj: Any) -> list[tuple[str, str]]:
    """Return (key_path, string_value) for every leaf."""
    out: list[tuple[str, str]] = []

    def walk(o: Any, path: str) -> None:
        if isinstance(o, dict):
            for k, v in o.items():
                walk(v, f"{path}.{k}" if path else str(k))
        elif isinstance(o, list | tuple):
            for i, v in enumerate(o):
                walk(v, f"{path}[{i}]")
        elif o is not None:
            out.append((path, str(o)))

    walk(obj, "")
    return out


def _flat_text(args: dict[str, Any]) -> str:
    return "\n".join(v for _, v in flatten(args))


def _policy(ctx: Ctx) -> dict[str, Any]:
    return ctx.app.get("tool_policy") or {}


def is_outbound(name: str, pol: dict[str, Any]) -> bool:
    return name in pol.get("outbound_tools", []) or bool(OUTBOUND_RE.search(name))


def destinations(args: dict[str, Any]) -> list[str]:
    dests: list[str] = []
    for path, val in flatten(args):
        key = re.split(r"[.\[]", path)[0].lower() if path else ""
        for m in re.finditer(r"[\w.+-]+@([\w-]+(?:\.[\w-]+)+)", val):
            dests.append(m.group(1).lower())
        for m in re.finditer(r"https?://[^\s\"']+", val):
            h = urlparse(m.group()).hostname
            if h:
                dests.append(h.lower())
        if key in DEST_KEYS and not re.search(r"[@/]", val) and re.fullmatch(r"[\w-]+(\.[\w-]+)+", val.strip()):
            dests.append(val.strip().lower())
    return sorted(set(dests))


def domain_allowed(host: str, allowed: list[str]) -> bool:
    return any(host == a.lower() or host.endswith("." + a.lower()) for a in allowed)


@register("TL-01", "PII or MNPI in tool arguments", "pattern")
def tl01(ctx: Ctx, rule: RuleConfig):
    flat = _flat_text(ctx.tool_args)
    pii = find_pii(flat)
    allow = set(rule.thresholds.get("allow_types", []))
    pii = [f for f in pii if f.kind not in allow]
    mn = in04(Ctx(text=flat, segments=[Segment("user", flat, 0)]), RuleConfig(id="IN-04", stage="input", severity="high", action="escalate"))
    ev = [f.masked for f in pii]
    if mn.status != "pass":
        ev += mn.evidence
        return make_result(rule, "PII or MNPI in tool arguments", "pattern", status="escalated", evidence=ev[:6], open_case=True,
                           explanation="Tool arguments appear to contain inside information; the call was held for compliance.",
                           safe_message="This action was held for Compliance review because it appears to involve inside information.")
    if not pii:
        return make_result(rule, "PII or MNPI in tool arguments", "pattern", explanation="No sensitive data in tool arguments.")
    modified = _redact_obj(ctx.tool_args, allow)
    return make_result(rule, "PII or MNPI in tool arguments", "pattern", status=violation_status(rule), evidence=ev[:8],
                       explanation="Sensitive identifiers in tool arguments were redacted before the tool runs.",
                       new_text=json.dumps(modified) if rule.action == "modify" else None)


def _redact_obj(o: Any, allow: set[str]) -> Any:
    if isinstance(o, dict):
        return {k: _redact_obj(v, allow) for k, v in o.items()}
    if isinstance(o, list):
        return [_redact_obj(v, allow) for v in o]
    if isinstance(o, str):
        return redact(o, [f for f in find_pii(o) if f.kind not in allow])
    return o


@register("TL-02", "Bulk export and exfiltration", "pattern")
def tl02(ctx: Ctx, rule: RuleConfig):
    ev: list[str] = []
    thr = int(rule.thresholds.get("row_limit", 100))
    for path, val in flatten(ctx.tool_args):
        key = path.lower()
        if re.search(r"(limit|count|max_rows|rows|page_size|top)$", key):
            try:
                if int(float(val)) > thr:
                    ev.append(f"{path}={val} exceeds row limit {thr}")
            except ValueError:
                pass
        if re.search(r"select\s+\*|\ball\s+(clients?|customers?|accounts?|records?|users?)\b|\bentire\s+(database|table|client|customer)|\bfull\s+(client|customer)\s+(list|database)", val, re.I):
            ev.append(f"{path}: broad data selection")
    if BULK_NAME_RE.search(ctx.tool_name):
        ev.append(f"bulk-style tool name '{ctx.tool_name}'")
    emails = len(re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+", _flat_text(ctx.tool_args)))
    if emails >= int(rule.thresholds.get("record_limit", 5)):
        ev.append(f"{emails} email addresses in one call (client-list pattern)")
    if len(ev) == 1 and ev[0].startswith("bulk-style tool name"):
        ev = []  # name alone is not enough
    if not ev:
        return make_result(rule, "Bulk export and exfiltration", "pattern", explanation="No bulk export or exfiltration pattern.")
    return make_result(rule, "Bulk export and exfiltration", "pattern", status=violation_status(rule), evidence=ev[:6],
                       explanation="The call matches a bulk data export / exfiltration pattern.",
                       safe_message="Bulk export of client data is not permitted through this tool.")


@register("TL-03", "Role and tool access", "deterministic")
def tl03(ctx: Ctx, rule: RuleConfig):
    pol = _policy(ctx)
    ev: list[str] = []
    if ctx.tool_name in pol.get("blocked_tools", []):
        ev.append(f"tool '{ctx.tool_name}' is blocked for this application")
    allowed = pol.get("allowed_tools")
    if allowed and ctx.tool_name not in allowed and ctx.tool_name not in pol.get("approval_required_tools", []):
        ev.append(f"tool '{ctx.tool_name}' is not on the application's allow-list")
    roles = pol.get("tool_roles", {}).get(ctx.tool_name)
    if roles and ctx.role not in roles:
        ev.append(f"role '{ctx.role}' may not use '{ctx.tool_name}'")
    for did in sorted(set(DOC_ID_RE.findall(_flat_text(ctx.tool_args).upper()))):
        doc = dataref.documents().get(did)
        if doc and not dataref.can_access(ctx.role, doc):
            ev.append(f"role '{ctx.role}' may not access {did}")
    if not ev:
        return make_result(rule, "Role and tool access", "deterministic", explanation="Tool and data access permitted for this role.")
    return make_result(rule, "Role and tool access", "deterministic", status=violation_status(rule), evidence=ev,
                       explanation="The application's tool policy or the user's role does not permit this call.",
                       safe_message="This tool call is not permitted for your role or application.")


@register("TL-04", "Injection text in tool arguments", "pattern")
def tl04(ctx: Ctx, rule: RuleConfig):
    ev = []
    for path, val in flatten(ctx.tool_args):
        for name, variant, snip in scan_injection(val):
            ev.append(f"{path}: {name} ({variant}) ...{snip}...")
    if ctx.context_text:
        for name, variant, snip in scan_injection(ctx.context_text):
            ev.append(f"recent context: {name} ({variant}) ...{snip}...")
    if not ev:
        return make_result(rule, "Injection text in tool arguments", "pattern", explanation="No injection text in arguments or recent context.")
    return make_result(rule, "Injection text in tool arguments", "pattern", status=violation_status(rule), evidence=ev[:5],
                       explanation="Instruction-like injection text accompanies this call, so the agent may have been hijacked.",
                       safe_message="This tool call was stopped because it appears to be driven by injected instructions.")


@register("TL-05", "Outbound destination allow-list", "deterministic")
def tl05(ctx: Ctx, rule: RuleConfig):
    pol = _policy(ctx)
    if not is_outbound(ctx.tool_name, pol):
        return make_result(rule, "Outbound destination allow-list", "deterministic", explanation="Not an outbound tool.")
    allowed = pol.get("allowed_outbound_domains", [])
    dests = destinations(ctx.tool_args)
    bad = [d for d in dests if not domain_allowed(d, allowed)]
    if not dests:
        return make_result(rule, "Outbound destination allow-list", "deterministic", explanation="Outbound tool with no identifiable destination.")
    if not bad:
        return make_result(rule, "Outbound destination allow-list", "deterministic", explanation=f"All destinations are allow-listed ({', '.join(dests)}).")
    return make_result(rule, "Outbound destination allow-list", "deterministic", status=violation_status(rule), evidence=[f"destination not allow-listed: {d}" for d in bad],
                       explanation="Outbound call targets a destination outside the application's allow-list (data exfiltration risk).",
                       safe_message="Sending data to that destination is not permitted.")


@register("TL-06", "High-impact action approval", "deterministic")
def tl06(ctx: Ctx, rule: RuleConfig):
    pol = _policy(ctx)
    hit = ctx.tool_name in pol.get("approval_required_tools", []) or bool(HIGH_IMPACT_RE.search(ctx.tool_name))
    if not hit:
        return make_result(rule, "High-impact action approval", "deterministic", explanation="Not a high-impact action.")
    return make_result(rule, "High-impact action approval", "deterministic", status=violation_status(rule), open_case=True,
                       evidence=[f"tool '{ctx.tool_name}' changes money or account state"],
                       explanation="Payments and account changes need explicit human approval before they run (EU AI Act human oversight).",
                       safe_message="This action needs human approval. A review case has been opened; poll the approval id.")


@register("TR-01", "Injection in tool results", "pattern")
def tr01(ctx: Ctx, rule: RuleConfig):
    ev = [f"{name} ({variant}) ...{snip}..." for name, variant, snip in scan_injection(ctx.text)]
    if not ev:
        return make_result(rule, "Injection in tool results", "pattern", explanation="No hidden instructions in the tool result.")
    return make_result(rule, "Injection in tool results", "pattern", status=violation_status(rule), evidence=ev[:5],
                       explanation="The tool result contains instructions aimed at the model (indirect prompt injection); it was not passed back.",
                       safe_message="[Tool result withheld: it contained instructions that attempt to control the assistant.]")


@register("TR-02", "Restricted data in tool results", "pattern")
def tr02(ctx: Ctx, rule: RuleConfig):
    ev = []
    for did, doc in dataref.documents().items():
        if (did in ctx.text or doc["title"].lower() in ctx.text.lower()) and not dataref.can_access(ctx.role, doc):
            ev.append(f"{did} ({doc['classification']}) not visible to role '{ctx.role}'")
    mn = in04(Ctx(text=ctx.text, segments=[Segment("user", ctx.text, 0)]), RuleConfig(id="IN-04", stage="input", severity="high", action="escalate"))
    if mn.status != "pass" and dataref.clearance(ctx.role) < 3:
        ev += mn.evidence
    if not ev:
        return make_result(rule, "Restricted data in tool results", "pattern", explanation="Nothing in the result exceeds the role's clearance.")
    return make_result(rule, "Restricted data in tool results", "pattern", status=violation_status(rule), evidence=ev[:5],
                       explanation="The result contains data this role may not see; it was withheld.",
                       safe_message="[Tool result withheld: it contains data your role is not permitted to see.]")
