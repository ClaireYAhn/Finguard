"""Rail engines. Both run the SAME check functions; the trace records which engine executed them.

- NemoEngine: NeMo Guardrails (Colang 1.0) input/output rails call a custom action that runs the checks.
- NativeEngine: calls the check functions directly. Used when FINGUARD_ENGINE=native, or when NeMo fails (the failure is recorded).
"""
from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from actions.base import ACTION_ORDER, CheckResult, Ctx, RuleConfig, run_check

log = logging.getLogger("finguard.engine")
# NeMo scans ./actions for its own @action modules and logs noisy (harmless) warnings about our check package.
for _n in ("nemoguardrails.actions.action_dispatcher", "nemoguardrails.actions"):
    logging.getLogger(_n).setLevel(logging.CRITICAL)
CONFIG_DIR = Path(__file__).resolve().parent.parent / "guardrails" / "config"
ACTION_FOR_STATUS = {"pass": "allow", "modified": "modify", "blocked": "block", "escalated": "escalate"}
OUTPUT_LAST = ("OUT-05",)


@dataclass
class StageOutcome:
    stage: str
    results: list[CheckResult] = field(default_factory=list)
    text: str = ""  # input stage: redacted latest user turn; output stage: final text before any safe-message override
    blocked: bool = False
    escalated: bool = False
    safe_message: str | None = None
    open_case: bool = False
    seg_updates: dict[int, str] = field(default_factory=dict)
    engine: str = "native"
    engine_note: str | None = None
    latency_ms: float = 0.0

    @property
    def action(self) -> str:
        if self.blocked:
            return "block"
        if self.escalated:
            return "escalate"
        return "modify" if any(r.status == "modified" for r in self.results) else "allow"


def order_rules(rules: list[RuleConfig], stage: str) -> list[RuleConfig]:
    rs = [r for r in rules if r.enabled]
    if stage == "output":
        rs.sort(key=lambda r: (r.id in OUTPUT_LAST, r.id))
    else:
        rs.sort(key=lambda r: r.id)
    return rs


def execute_rules(stage: str, ctx: Ctx, rules: list[RuleConfig]) -> StageOutcome:
    """Run enabled rules in order. A failing check never crashes the request (see actions.base.run_check)."""
    t0 = time.perf_counter()
    out = StageOutcome(stage=stage)
    for rule in order_rules(rules, stage):
        res = run_check(rule, ctx)
        out.results.append(res)
        if res.status == "modified" and res.new_text is not None and stage == "output":
            ctx.output = res.new_text
        if res.status == "blocked":
            out.blocked = True
            out.safe_message = out.safe_message or res.safe_message
        elif res.status == "escalated":
            out.escalated = True
        if res.open_case or res.status == "escalated":
            out.open_case = True
    # blocked takes precedence over escalated for the message shown
    if out.blocked:
        first = next(r for r in out.results if r.status == "blocked")
        out.safe_message = first.safe_message or "This request was blocked by policy."
    elif out.escalated:
        first = next((r for r in out.results if r.status == "escalated" and r.safe_message), None)
        out.safe_message = first.safe_message if first else "This has been passed to our team for review."
    if stage == "output":
        out.text = ctx.output
    else:
        out.seg_updates = dict(ctx.seg_updates)
        out.text = ctx.seg_updates.get(ctx.segments[-1].index, ctx.text) if ctx.segments else ctx.text
    out.latency_ms = round((time.perf_counter() - t0) * 1000, 3)
    return out


class NativeEngine:
    name = "native"

    async def run(self, stage: str, ctx: Ctx, rules: list[RuleConfig]) -> StageOutcome:
        out = execute_rules(stage, ctx, rules)
        out.engine = "native"
        return out


class NemoEngine:
    name = "nemo"

    def __init__(self) -> None:
        self._rails: Any = None
        self._pending: dict[str, dict[str, Any]] = {}
        self.load_error: str | None = None
        self.version: str | None = None

    def _load(self) -> Any:
        if self._rails is not None:
            return self._rails
        import nemoguardrails
        from nemoguardrails import LLMRails, RailsConfig  # VERIFY AGAINST DOCS: 0.24.1 public API

        self.version = getattr(nemoguardrails, "__version__", None)
        rails = LLMRails(RailsConfig.from_path(str(CONFIG_DIR)))

        async def finguard_input_rails(run_id: str | None = None) -> dict[str, bool]:
            return self._action("input", run_id)

        async def finguard_output_rails(run_id: str | None = None) -> dict[str, bool]:
            return self._action("output", run_id)

        rails.register_action(finguard_input_rails, "finguard_input_rails")
        rails.register_action(finguard_output_rails, "finguard_output_rails")
        self._rails = rails
        return rails

    def _action(self, stage: str, run_id: str | None) -> dict[str, bool]:
        slot = self._pending[str(run_id)]
        out = execute_rules(stage, slot["ctx"], slot["rules"])
        slot["outcome"] = out
        return {"blocked": out.blocked or out.escalated}

    async def run(self, stage: str, ctx: Ctx, rules: list[RuleConfig]) -> StageOutcome:
        run_id = uuid.uuid4().hex
        self._pending[run_id] = {"ctx": ctx, "rules": rules, "outcome": None}
        try:
            rails = self._load()
            msgs: list[dict[str, Any]] = [{"role": "context", "content": {"fg_run": run_id}}, {"role": "user", "content": ctx.user_input or ctx.text or " "}]
            nemo_rail = "output" if stage == "output" else "input"  # tool-stage checks ride on the input rail
            if stage == "output":
                msgs.append({"role": "assistant", "content": ctx.output or " "})
            res = await rails.generate_async(messages=msgs, options={"rails": [nemo_rail]})
            out = self._pending[run_id]["outcome"]
            if out is None:
                raise RuntimeError("NeMo did not execute the FinGuard rail action")
            content = res.response[0]["content"] if isinstance(res.response, list) and res.response else str(res.response)
            nemo_stopped = content == "FINGUARD_STOP"
            if nemo_stopped != (out.blocked or out.escalated):
                raise RuntimeError(f"NeMo decision ({nemo_stopped}) disagrees with check outcome")
            out.engine = "nemo"
            return out
        except Exception as exc:  # noqa: BLE001 - fall back, never skip silently
            self.load_error = f"{type(exc).__name__}: {exc}"
            log.warning("NeMo engine failed, falling back to native: %s", self.load_error)
            slot = self._pending[run_id]
            out = execute_rules(stage, slot["ctx"], slot["rules"]) if slot["outcome"] is None else slot["outcome"]
            out.engine = "native"
            out.engine_note = f"NeMo failed: {self.load_error}"
            return out
        finally:
            self._pending.pop(run_id, None)


_nemo = NemoEngine()
_native = NativeEngine()


def get_engine(name: str) -> NativeEngine | NemoEngine:
    return _nemo if name == "nemo" else _native


def engine_status() -> dict[str, Any]:
    return {"nemo_loaded": _nemo._rails is not None, "nemo_version": _nemo.version, "last_error": _nemo.load_error}


__all__ = ["ACTION_FOR_STATUS", "ACTION_ORDER", "NativeEngine", "NemoEngine", "StageOutcome", "engine_status", "execute_rules", "get_engine"]
