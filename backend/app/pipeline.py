"""Governance pipeline: input rails -> model -> output rails -> audit (+ review case)."""
from __future__ import annotations

import copy
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import actions  # noqa: F401  (registers all checks)
from actions.base import Ctx, Segment
from audit import store as audit
from policies import store as policies

from .config import get_settings
from .engines import StageOutcome, get_engine
from .judge import make_judge
from .providers import ProviderRequest, ProviderResponse, complete, default_model_for, is_mock, provider_name

INPUT_STAGES = {"input", "dialogue", "retrieval"}
CASE_KIND = {"IN-04": "mnpi", "OUT-06": "vulnerability", "OUT-09": "tipping-off", "OUT-08": "fairness", "OUT-10": "explainability", "TL-06": "tool_approval", "TL-01": "mnpi"}
PRECEDENCE = {"allow": 0, "modify": 1, "escalate": 2, "block": 3}


class UpstreamError(Exception):
    def __init__(self, message: str, status: int = 502) -> None:
        super().__init__(message)
        self.status = status


@dataclass
class Conversation:
    """A provider-format request, parsed into checkable segments, with setters to write redacted text back."""

    fmt: str  # anthropic | openai | plain
    model: str
    max_tokens: int
    segments: list[Segment]
    payload: dict[str, Any]
    setters: dict[int, Callable[[str], None]] = field(default_factory=dict)
    stream: bool = False

    @property
    def latest_user(self) -> Segment | None:
        for s in reversed(self.segments):
            if s.kind == "user":
                return s
        return None

    def flat(self, updates: dict[int, str] | None = None) -> tuple[str, list[dict[str, str]]]:
        """Text-only (system, messages) view, applying redaction updates. Used by the mock provider and audit."""
        updates = updates or {}
        system_parts: list[str] = []
        msgs: list[dict[str, str]] = []
        last_key: tuple[int, str] | None = None
        for s in self.segments:
            text = updates.get(s.index, s.text)
            if s.kind == "system":
                system_parts.append(text)
                continue
            role = "assistant" if s.kind == "assistant" else "user"
            if s.kind == "tool_result":
                text = f"[tool result]\n{text}"
            elif s.kind == "document":
                text = f"[document]\n{text}"
            key = (s.msg, role)
            if msgs and last_key == key:
                msgs[-1]["content"] += "\n" + text
            else:
                msgs.append({"role": role, "content": text})
            last_key = key
        return "\n".join(system_parts), msgs

    def ensure_system(self, default: str) -> None:
        if not default or any(s.kind == "system" for s in self.segments):
            return
        idx = max((s.index for s in self.segments), default=-1) + 1
        self.segments.insert(0, Segment("system", default, idx, -1))
        if self.fmt == "anthropic":
            self.payload["system"] = default
        elif self.fmt == "openai":
            self.payload.setdefault("messages", []).insert(0, {"role": "system", "content": default})


@dataclass
class GovernResult:
    audit_id: str | None
    action: str
    final_text: str
    model_called: bool
    results: list[dict[str, Any]]
    rules_fired: list[str]
    engine: str
    pack: str
    pack_version: int
    latency: dict[str, float]
    model: str
    raw_output: str | None
    redacted_input: str
    model_input: str  # exactly what the provider received (for evaluation: did MNPI/PII reach the model?)
    case_id: str | None = None
    provider: ProviderResponse | None = None
    stop_reason: str = "end_turn"
    blocked_at: str | None = None
    refusal: bool = False

    def headers(self) -> dict[str, str]:
        return {"X-FinGuard-Action": self.action, "X-FinGuard-Request-Id": self.audit_id or "", "X-FinGuard-Rules": ",".join(self.rules_fired) or "none",
                "X-FinGuard-Engine": self.engine, "X-FinGuard-Policy-Version": f"{self.pack}@{self.pack_version}"}


def _dump(results: list) -> list[dict[str, Any]]:
    return [r.model_dump() for r in results]


def _fired(rs: list[dict[str, Any]]) -> list[str]:
    return [r["rule_id"] for r in rs if r["status"] != "pass"]


def _open_case(app: dict[str, Any], audit_rec: dict[str, Any], rs: list[dict[str, Any]], payload: dict[str, Any]) -> str:
    trig = [r for r in rs if r["status"] == "escalated"] or [r for r in rs if r["status"] in ("modified",) and r["rule_id"] == "OUT-06"] or rs[:1]
    first = trig[0]["rule_id"] if trig else "?"
    case = audit.create_case(audit_id=audit_rec["id"], app_id=app.get("id"), app_name=app.get("name", ""), kind=CASE_KIND.get(first, "content"),
                             reason="; ".join(t["explanation"] for t in trig)[:500], rule_ids=[t["rule_id"] for t in trig],
                             severity=trig[0]["severity"] if trig else "high", payload=payload)
    return case["id"]


async def govern(*, app: dict[str, Any], conv: Conversation, role: str, user: str, channel: str = "gateway", guardrails: bool = True,
                 engine_name: str | None = None) -> GovernResult:
    """Run one chat-style request through FinGuard. With guardrails=False it only calls the model (used for 'off' comparisons)."""
    t_all = time.perf_counter()
    pack = policies.get_pack(app["policy_pack"]) or policies.get_pack("internal_staff")
    assert pack is not None
    settings = dict(pack.get("settings", {}))
    settings["use_presidio"] = get_settings().use_presidio
    rules = policies.rule_configs(pack)
    model = conv.model or app.get("model") or default_model_for(conv.fmt)
    conv.ensure_system(settings.get("default_system_prompt", ""))
    latest = conv.latest_user
    user_text = latest.text if latest else ""
    engine = get_engine(engine_name or get_settings().engine)
    lat: dict[str, float] = {}

    ctx = Ctx(text=user_text, segments=conv.segments, user_input=user_text, role=role, app=app, settings=settings, provider_is_mock=is_mock(), judge=make_judge())
    updates: dict[int, str] = {}
    in_out: StageOutcome | None = None
    in_results: list[dict[str, Any]] = []
    engine_used, notes = "off", []

    if guardrails:
        in_rules = [r for r in rules if r.stage in INPUT_STAGES]
        t0 = time.perf_counter()
        in_out = await engine.run("input", ctx, in_rules)
        lat["input_ms"] = round((time.perf_counter() - t0) * 1000, 3)
        in_results = _dump(in_out.results)
        updates = in_out.seg_updates
        engine_used = in_out.engine
        if in_out.engine_note:
            notes.append(in_out.engine_note)
    redacted_latest = updates.get(latest.index, user_text) if latest else ""

    raw_output: str | None = None
    prov: ProviderResponse | None = None
    out_out: StageOutcome | None = None
    out_results: list[dict[str, Any]] = []
    model_input = ""
    final_text, action, blocked_at = "", "allow", None

    if guardrails and in_out and (in_out.blocked or in_out.escalated):
        final_text = in_out.safe_message or "This request cannot be processed."
        action = in_out.action
        blocked_at = "input"
        sys_txt, msgs = conv.flat(updates)
    else:
        for idx, text in updates.items():
            if idx in conv.setters:
                conv.setters[idx](text)
        sys_txt, msgs = conv.flat(updates)
        model_input = (sys_txt + "\n" + "\n".join(m["content"] for m in msgs)).strip()
        t0 = time.perf_counter()
        try:
            prov = await complete(ProviderRequest(model=model, system=sys_txt, messages=msgs, max_tokens=conv.max_tokens, raw_payload=conv.payload, fmt=conv.fmt))
        except Exception as exc:  # noqa: BLE001
            lat["model_ms"] = round((time.perf_counter() - t0) * 1000, 3)
            if guardrails:
                rec = audit.write_audit(app_id=app.get("id"), app_name=app.get("name", ""), user=user, role=role, channel=channel, original_input=user_text,
                                        redacted_input=redacted_latest, raw_output=None, final_output=None, rule_results=in_results, final_action="error",
                                        latency=lat, pack=pack["pack"], pack_version=pack["version"], model=model, engine=engine_used,
                                        extra={"error": f"{type(exc).__name__}: {exc}", "provider": provider_name()})
                raise UpstreamError(f"Upstream model error: {exc}") from exc
            raise UpstreamError(f"Upstream model error: {exc}") from exc
        lat["model_ms"] = round((time.perf_counter() - t0) * 1000, 3)
        raw_output = prov.text
        model = prov.model or model
        final_text = raw_output
        if guardrails:
            ctx.output = raw_output
            out_rules = [r for r in rules if r.stage == "output"]
            t0 = time.perf_counter()
            out_out = await engine.run("output", ctx, out_rules)
            lat["output_ms"] = round((time.perf_counter() - t0) * 1000, 3)
            out_results = _dump(out_out.results)
            if out_out.engine_note:
                notes.append(out_out.engine_note)
            engine_used = "native" if "native" in (in_out.engine if in_out else "", out_out.engine) else out_out.engine
            if out_out.blocked or out_out.escalated:
                final_text = out_out.safe_message or "This response was withheld."
                blocked_at = "output"
            else:
                final_text = out_out.text
            action = out_out.action
        if in_out and PRECEDENCE[in_out.action] > PRECEDENCE[action]:
            action = in_out.action

    if guardrails and in_out and PRECEDENCE[in_out.action] > PRECEDENCE[action]:
        action = in_out.action
    results = in_results + out_results
    lat["total_ms"] = round((time.perf_counter() - t_all) * 1000, 3)
    audit_id, case_id = None, None
    if guardrails:
        rec = audit.write_audit(app_id=app.get("id"), app_name=app.get("name", ""), user=user, role=role, channel=channel, original_input=user_text,
                                redacted_input=redacted_latest, raw_output=raw_output, final_output=final_text, rule_results=results,
                                final_action=action, latency=lat, pack=pack["pack"], pack_version=pack["version"], model=model, engine=engine_used,
                                extra={"provider": provider_name(), "turns": len([s for s in conv.segments if s.kind in ("user", "assistant")]),
                                       "model_called": bool(prov), "blocked_at": blocked_at, "engine_notes": notes,
                                       "in_tokens": prov.input_tokens if prov else 0, "out_tokens": prov.output_tokens if prov else 0})
        audit_id = rec["id"]
        if (in_out and in_out.open_case) or (out_out and out_out.open_case):
            case_id = _open_case(app, rec, results, {"input": redacted_latest, "proposed_output": audit.storage_redact(raw_output), "final_output": final_text})
    return GovernResult(audit_id=audit_id, action=action, final_text=final_text, model_called=prov is not None, results=results,
                        rules_fired=_fired(results), engine=engine_used, pack=pack["pack"], pack_version=pack["version"], latency=lat, model=model,
                        raw_output=raw_output, redacted_input=redacted_latest, model_input=model_input, case_id=case_id, provider=prov,
                        stop_reason=prov.stop_reason if prov else "end_turn", blocked_at=blocked_at, refusal=blocked_at is not None)


def plain_conversation(text: str, *, model: str = "", system: str | None = None, history: list[dict[str, str]] | None = None) -> Conversation:
    """Build a Conversation from plain text (demo, evaluation, simulator)."""
    segs: list[Segment] = []
    payload: dict[str, Any] = {"model": model, "max_tokens": 1024, "messages": []}
    setters: dict[int, Callable[[str], None]] = {}
    i = 0
    if system:
        segs.append(Segment("system", system, i, -1)); payload["system"] = system; i += 1
    for h in history or []:
        segs.append(Segment("assistant" if h["role"] == "assistant" else "user", h["content"], i, len(payload["messages"])))
        payload["messages"].append({"role": h["role"], "content": h["content"]}); i += 1
    segs.append(Segment("user", text, i, len(payload["messages"])))
    payload["messages"].append({"role": "user", "content": text})
    return Conversation("anthropic", model, 1024, segs, copy.deepcopy(payload), setters)
