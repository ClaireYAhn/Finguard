"""Shared types for FinGuard checks. Every check returns a CheckResult."""
from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2}
ACTION_ORDER = {"allow": 0, "log": 0, "modify": 1, "escalate": 2, "block": 3}


class RegRef(BaseModel):
    ref: str
    why: str = ""


class CheckResult(BaseModel):
    rule_id: str
    name: str
    stage: str  # input | dialogue | retrieval | output | tool
    status: str = "pass"  # pass | modified | blocked | escalated
    severity: str = "low"
    explanation: str = ""
    regulations: list[RegRef] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    latency_ms: float = 0.0
    check_type: str = "deterministic"  # deterministic | pattern | model
    error: str | None = None
    # internal-only payload (not persisted in rule results): replacement text etc.
    new_text: str | None = Field(default=None, exclude=True)
    safe_message: str | None = Field(default=None, exclude=True)
    open_case: bool = Field(default=False, exclude=True)


@dataclass
class Segment:
    kind: str  # user | assistant | system | tool_result | document
    text: str
    index: int = 0
    msg: int = 0  # index of the originating message (used to rebuild a text-only conversation)


@dataclass
class RuleConfig:
    id: str
    description: str = ""
    stage: str = "input"
    enabled: bool = True
    severity: str = "medium"
    action: str = "log"  # allow | modify | block | escalate | log
    thresholds: dict[str, Any] = field(default_factory=dict)
    regulations: list[RegRef] = field(default_factory=list)
    name: str = ""


@dataclass
class Ctx:
    """Everything a check may look at."""

    text: str  # the text under test (user turn for input stage, model output for output stage)
    segments: list[Segment] = field(default_factory=list)
    user_input: str = ""  # latest user turn (original)
    output: str = ""
    role: str = "client"
    app: dict[str, Any] = field(default_factory=dict)
    settings: dict[str, Any] = field(default_factory=dict)  # pack settings
    provider_is_mock: bool = True
    # tool stage
    tool_name: str = ""
    tool_args: dict[str, Any] = field(default_factory=dict)
    # filled during the run
    redacted_input: str = ""
    seg_updates: dict[int, str] = field(default_factory=dict)  # segment index -> redacted text
    judge: Callable[[str, str], dict[str, Any]] | None = None

    @property
    def history_user_text(self) -> str:
        return "\n".join(s.text for s in self.segments if s.kind == "user")

    @property
    def context_text(self) -> str:
        return "\n".join(s.text for s in self.segments)


CheckFn = Callable[[Ctx, RuleConfig], CheckResult]
CHECKS: dict[str, tuple[CheckFn, str, str]] = {}  # rule_id -> (fn, name, check_type)


def register(rule_id: str, name: str, check_type: str = "pattern"):
    def deco(fn: CheckFn) -> CheckFn:
        CHECKS[rule_id] = (fn, name, check_type)
        return fn

    return deco


def make_result(rule: RuleConfig, name: str, check_type: str, **kw: Any) -> CheckResult:
    return CheckResult(
        rule_id=rule.id,
        name=name,
        stage=rule.stage,
        severity=rule.severity,
        regulations=rule.regulations,
        check_type=check_type,
        **kw,
    )


def violation_status(rule: RuleConfig) -> str:
    return {"modify": "modified", "block": "blocked", "escalate": "escalated"}.get(rule.action, "pass")


def run_check(rule: RuleConfig, ctx: Ctx) -> CheckResult:
    """Run one check; never raises. High severity errors fail closed, others are skipped."""
    fn, name, ctype = CHECKS[rule.id]
    t0 = time.perf_counter()
    try:
        res = fn(ctx, rule)
    except Exception as exc:  # noqa: BLE001 - a failing check must never crash a request
        if rule.severity == "high":
            res = make_result(
                rule, name, ctype, status="blocked",
                explanation="Check errored; failing closed because severity is high.",
                error=f"{type(exc).__name__}: {exc}", evidence=["check error"],
                safe_message="This request could not be safely checked and was stopped.",
            )
        else:
            res = make_result(
                rule, name, ctype, status="pass",
                explanation="Check errored and was skipped (severity below high).",
                error=f"{type(exc).__name__}: {exc}",
            )
    res.latency_ms = round((time.perf_counter() - t0) * 1000, 3)
    return res


def load_json(name: str) -> Any:
    return json.loads((DATA_DIR / name).read_text())
