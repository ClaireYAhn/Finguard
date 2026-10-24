"""Agent guard endpoints: /v1/guard/tool-call, /v1/guard/tool-result, /v1/guard/prompt, /v1/guard/approvals/{id}."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from actions.base import Ctx
from audit import store as audit
from gateway.routes import resolve_identity
from policies import store as policies

from .auth import AuthError, authenticate_app
from .config import get_settings
from .engines import get_engine
from .pipeline import _dump, _fired
from .toolguard import guard_tool

router = APIRouter(prefix="/v1/guard")


class ToolCallIn(BaseModel):
    agent_id: str = "agent"
    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    user: str | None = None
    role: str | None = None
    context: list[str] = Field(default_factory=list)
    app_key: str | None = None


class ToolResultIn(BaseModel):
    agent_id: str = "agent"
    tool: str
    result: Any = ""
    user: str | None = None
    role: str | None = None
    app_key: str | None = None


class PromptIn(BaseModel):
    text: str
    user: str | None = None
    role: str | None = None
    app_key: str | None = None


def _auth(request: Request, body_key: str | None) -> dict[str, Any]:
    if body_key and not request.headers.get("x-api-key") and not request.headers.get("authorization"):
        from registry import store as registry

        app = registry.get_by_key(body_key)
        if not app or not app["enabled"]:
            raise AuthError("Invalid or disabled FinGuard app key.")
        return app
    return authenticate_app(request)


def _ident(request: Request, app: dict[str, Any], user: str | None, role: str | None) -> tuple[str, str, str]:
    u, r, ch = resolve_identity(request, app)
    return user or u, role or r, ch if request.headers.get("x-finguard-channel") else "tool-call"


def _sim(request: Request, channel: str) -> None:
    if channel == "simulated":
        try:
            audit.ts_offset_minutes.set(float(request.headers.get("x-finguard-sim-offset-minutes", 0)))
        except ValueError:
            pass


@router.post("/tool-call")
async def tool_call(body: ToolCallIn, request: Request) -> Any:
    try:
        app = _auth(request, body.app_key)
    except AuthError as e:
        return JSONResponse({"error": str(e)}, status_code=e.status)
    user, role, channel = _ident(request, app, body.user, body.role)
    _sim(request, channel)
    return await guard_tool(app=app, kind="call", tool=body.tool, args=body.arguments, result_text=None, agent_id=body.agent_id, user=user, role=role,
                            context=body.context, channel=channel)


@router.post("/tool-result")
async def tool_result(body: ToolResultIn, request: Request) -> Any:
    try:
        app = _auth(request, body.app_key)
    except AuthError as e:
        return JSONResponse({"error": str(e)}, status_code=e.status)
    user, role, channel = _ident(request, app, body.user, body.role)
    _sim(request, channel)
    text = body.result if isinstance(body.result, str) else __import__("json").dumps(body.result)
    return await guard_tool(app=app, kind="result", tool=body.tool, args=None, result_text=text, agent_id=body.agent_id, user=user, role=role, context=None, channel=channel)


@router.post("/prompt")
async def prompt_check(body: PromptIn, request: Request) -> Any:
    """Input rails only (no model call). Used by the Claude Code UserPromptSubmit hook."""
    try:
        app = _auth(request, body.app_key)
    except AuthError as e:
        return JSONResponse({"error": str(e)}, status_code=e.status)
    user, role, _ = _ident(request, app, body.user, body.role)
    channel = (request.headers.get("x-finguard-channel") or "hook").lower()
    channel = channel if channel in ("hook", "simulated", "gateway") else "hook"
    _sim(request, channel)
    pack = policies.get_pack(app["policy_pack"]) or policies.get_pack("internal_staff")
    assert pack is not None
    from actions.base import Segment

    rules = [r for r in policies.rule_configs(pack) if r.stage in ("input", "dialogue", "retrieval")]
    ctx = Ctx(text=body.text, segments=[Segment("user", body.text, 0)], user_input=body.text, role=role, app=app, settings={**pack.get("settings", {}), "use_presidio": get_settings().use_presidio})
    out = await get_engine(get_settings().engine).run("input", ctx, rules)
    results = _dump(out.results)
    rec = audit.write_audit(app_id=app["id"], app_name=app["name"], user=user, role=role, channel=channel, original_input=body.text, redacted_input=out.text,
                            raw_output=None, final_output=out.safe_message if out.action in ("block", "escalate") else None, rule_results=results, final_action=out.action,
                            latency={"input_ms": out.latency_ms}, pack=pack["pack"], pack_version=pack["version"], model="", engine=out.engine, extra={"hook": "UserPromptSubmit"})
    case_id = None
    if out.escalated:
        case_id = audit.create_case(audit_id=rec["id"], app_id=app["id"], app_name=app["name"], kind="mnpi", reason="Prompt escalated by input rails",
                                    rule_ids=_fired(results), payload={"input": out.text})["id"]
    return {"decision": out.action, "request_id": rec["id"], "redacted_text": out.text, "case_id": case_id, "message": out.safe_message,
            "reasons": [{"rule_id": r["rule_id"], "name": r["name"], "status": r["status"], "explanation": r["explanation"], "evidence": r["evidence"]} for r in results if r["status"] != "pass"],
            "engine": out.engine}


@router.get("/approvals/{approval_id}")
async def approval_status(approval_id: str, request: Request) -> Any:
    try:
        app = authenticate_app(request)
    except AuthError as e:
        return JSONResponse({"error": str(e)}, status_code=e.status)
    case = audit.get_case(approval_id)
    if not case or case["app_id"] != app["id"]:
        return JSONResponse({"error": "Unknown approval id."}, status_code=404)
    status = {"open": "pending"}.get(case["status"], case["status"])
    return {"id": case["id"], "status": status, "note": case.get("reviewer_note"), "decided_at": case.get("decided_at")}
