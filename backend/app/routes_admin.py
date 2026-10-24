"""Control-panel API (all under /api, admin session cookie required except /api/config and /api/auth/*)."""
from __future__ import annotations

import json
import time
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from audit import store as audit
from eval import runner as eval_runner
from policies import store as policies
from registry import store as registry
from registry.templates import TEMPLATES

from . import demo, providers, reports, stats
from .auth import COOKIE, SESSION_TTL, check_password, make_session, require_admin, verify_session
from .config import get_settings
from .engines import engine_status
from .pipeline import govern, plain_conversation
from .seed import seed_demo_apps

public = APIRouter(prefix="/api")
router = APIRouter(prefix="/api", dependencies=[Depends(require_admin)])

VERSION = "0.1.0"
SERVER_START = time.time()


# ----------------------------------------------------------------- public
@public.get("/config")
async def config(request: Request) -> dict[str, Any]:
    s = get_settings()
    base = s.public_url.rstrip("/") or str(request.base_url).rstrip("/")
    return {"version": VERSION, "provider": s.provider, "mock": providers.is_mock(), "engine": s.engine, "store_raw": s.store_raw, "model_judge": s.model_judge,
            "public_url": base, "banner": "Demo data is fictional. Not financial, legal or regulatory advice.", "engine_status": engine_status(),
            "signed_in": verify_session(request.cookies.get(COOKIE)),
            "scope_note": "FinGuard covers AI routes the firm controls (API gateway, Claude Code hooks, agent tool layer). It cannot filter public consumer apps such as the claude.ai website, because that traffic never passes through the firm."}


class LoginIn(BaseModel):
    password: str


@public.post("/auth/login")
async def login(body: LoginIn, request: Request, response: Response) -> dict[str, bool]:
    if not check_password(body.password, request.client.host if request.client else "?"):
        raise HTTPException(401, "That password is not correct.")
    response.set_cookie(COOKIE, make_session(), httponly=True, samesite="lax", max_age=SESSION_TTL, path="/")
    return {"ok": True}


@public.post("/auth/logout")
async def logout(response: Response) -> dict[str, bool]:
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@public.get("/healthz")
async def healthz() -> dict[str, Any]:
    return {"ok": True, "uptime_s": round(time.time() - SERVER_START, 1)}


# ----------------------------------------------------------------- apps
class AppIn(BaseModel):
    name: str
    owner: str = ""
    business_unit: str = ""
    description: str = ""
    risk_tier: str = "limited"
    eu_ai_act_note: str = ""
    model: str = "claude-sonnet-5-5"
    data_classes: list[str] = Field(default_factory=list)
    policy_pack: str = "internal_staff"
    allowed_roles: list[str] = Field(default_factory=list)
    default_role: str = "staff"
    tool_policy: dict[str, Any] = Field(default_factory=dict)


class AppPatch(BaseModel):
    name: str | None = None
    owner: str | None = None
    business_unit: str | None = None
    description: str | None = None
    risk_tier: str | None = None
    eu_ai_act_note: str | None = None
    model: str | None = None
    data_classes: list[str] | None = None
    policy_pack: str | None = None
    allowed_roles: list[str] | None = None
    default_role: str | None = None
    tool_policy: dict[str, Any] | None = None
    enabled: bool | None = None


class FromTemplate(BaseModel):
    template: str
    name: str | None = None
    owner: str = ""
    business_unit: str = ""


@router.get("/templates")
async def templates() -> list[dict[str, Any]]:
    return [{"key": k, **{f: v[f] for f in ("name", "description", "risk_tier", "eu_ai_act_note", "model", "data_classes", "allowed_roles", "default_role", "tool_policy")}} for k, v in TEMPLATES.items()]


@router.get("/apps")
async def list_apps() -> list[dict[str, Any]]:
    act = stats.app_activity(7)
    out = []
    for a in registry.list_apps():
        s = act.get(a["id"], {})
        out.append({**a, "requests_7d": s.get("requests", 0), "blocked_7d": s.get("blocked", 0), "last_activity": s.get("last_activity")})
    return out


@router.post("/apps")
async def create_app(body: AppIn) -> dict[str, Any]:
    if body.policy_pack not in {p["pack"] for p in policies.list_packs()}:
        raise HTTPException(422, f"Unknown policy pack '{body.policy_pack}'.")
    app, key = registry.create_app(**body.model_dump())
    return {"app": app, "key": key, "key_notice": "Copy this key now. FinGuard stores only a hash and cannot show it again."}


@router.post("/apps/from-template")
async def from_template(body: FromTemplate) -> dict[str, Any]:
    if body.template not in TEMPLATES:
        raise HTTPException(404, "Unknown template.")
    app, key = registry.create_from_template(body.template, name=body.name, owner=body.owner, business_unit=body.business_unit)
    return {"app": app, "key": key, "key_notice": "Copy this key now. FinGuard stores only a hash and cannot show it again."}


@router.get("/apps/{app_id}")
async def get_app(app_id: str) -> dict[str, Any]:
    app = registry.get_app(app_id)
    if not app:
        raise HTTPException(404, "Application not found.")
    return app


@router.patch("/apps/{app_id}")
async def patch_app(app_id: str, body: AppPatch) -> dict[str, Any]:
    if not registry.get_app(app_id):
        raise HTTPException(404, "Application not found.")
    return registry.update_app(app_id, body.model_dump(exclude_none=True))  # type: ignore[return-value]


@router.delete("/apps/{app_id}")
async def delete_app(app_id: str) -> dict[str, bool]:
    if not registry.delete_app(app_id):
        raise HTTPException(404, "Application not found.")
    return {"ok": True}


@router.post("/apps/{app_id}/rotate-key")
async def rotate(app_id: str) -> dict[str, Any]:
    r = registry.rotate_key(app_id)
    if not r:
        raise HTTPException(404, "Application not found.")
    return {"app": r[0], "key": r[1], "key_notice": "The previous key no longer works. Copy this one now."}


class TestIn(BaseModel):
    message: str
    role: str | None = None
    user: str = "control-panel"


@router.post("/apps/{app_id}/test")
async def test_app(app_id: str, body: TestIn) -> dict[str, Any]:
    app = registry.get_app(app_id)
    if not app:
        raise HTTPException(404, "Application not found.")
    if not app["enabled"]:
        raise HTTPException(409, "This application is disabled. Enable it to send a test request.")
    res = await govern(app=app, conv=plain_conversation(body.message), role=body.role or app["default_role"], user=body.user, channel="demo")
    return {"action": res.action, "text": res.final_text, "rules_fired": res.rules_fired, "trace": res.results, "audit_id": res.audit_id, "case_id": res.case_id,
            "engine": res.engine, "latency": res.latency, "pack": f"{res.pack}@{res.pack_version}", "headers": res.headers(), "note": "Sent from the control panel (channel=demo), not through the HTTP gateway."}


# ----------------------------------------------------------------- policies
@router.get("/policies")
async def policy_list() -> list[dict[str, Any]]:
    return policies.list_packs()


@router.get("/policies/{pack}")
async def policy_get(pack: str, version: int | None = None) -> dict[str, Any]:
    p = policies.get_pack(pack, version)
    if not p:
        raise HTTPException(404, "Policy pack not found.")
    return p


class PolicyEdit(BaseModel):
    pack: dict[str, Any]
    note: str = ""


@router.put("/policies/{pack}")
async def policy_put(pack: str, body: PolicyEdit) -> dict[str, Any]:
    try:
        return policies.save_new_version(pack, body.pack, "admin", body.note)
    except KeyError:
        raise HTTPException(404, "Policy pack not found.") from None
    except Exception as e:  # noqa: BLE001
        raise HTTPException(422, f"Invalid policy: {e}") from e


@router.get("/policies/{pack}/history")
async def policy_history(pack: str) -> list[dict[str, Any]]:
    return policies.history(pack)


@router.get("/policies/{pack}/diff")
async def policy_diff(pack: str, from_version: int = Query(alias="from"), to_version: int = Query(alias="to")) -> dict[str, Any]:
    try:
        return policies.diff(pack, from_version, to_version)
    except KeyError:
        raise HTTPException(404, "Version not found.") from None


class RollbackIn(BaseModel):
    version: int


@router.post("/policies/{pack}/rollback")
async def policy_rollback(pack: str, body: RollbackIn) -> dict[str, Any]:
    try:
        return policies.rollback(pack, body.version)
    except KeyError:
        raise HTTPException(404, "Version not found.") from None


# ----------------------------------------------------------------- audit and reviews
@router.get("/audit")
async def audit_list(app_id: str | None = None, action: str | None = None, rule: str | None = None, severity: str | None = None, channel: str | None = None,
                     date_from: str | None = Query(None, alias="from"), date_to: str | None = Query(None, alias="to"), q: str | None = None,
                     limit: int = Query(100, le=1000), offset: int = 0) -> list[dict[str, Any]]:
    return audit.query_records(app_id=app_id, action=action, rule=rule, severity=severity, channel=channel, date_from=date_from, date_to=date_to, q=q, limit=limit, offset=offset)


@router.get("/audit/verify")
async def audit_verify() -> dict[str, Any]:
    return audit.verify_chain()


@router.get("/audit/export")
async def audit_export(format: str = "json", app_id: str | None = None, action: str | None = None, rule: str | None = None, severity: str | None = None,
                       channel: str | None = None, date_from: str | None = Query(None, alias="from"), date_to: str | None = Query(None, alias="to")) -> Response:
    rows = audit.query_records(app_id=app_id, action=action, rule=rule, severity=severity, channel=channel, date_from=date_from, date_to=date_to, limit=100000)
    if format == "csv":
        return Response(audit.export_csv(rows), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=finguard-audit.csv"})
    return Response(json.dumps({"head_hash": audit.head_hash(), "records": rows}, indent=1), media_type="application/json",
                    headers={"Content-Disposition": "attachment; filename=finguard-audit.json"})


@router.get("/audit/{audit_id}")
async def audit_get(audit_id: str) -> dict[str, Any]:
    r = audit.get_record(audit_id)
    if not r:
        raise HTTPException(404, "Audit record not found.")
    return r


@router.get("/reviews")
async def reviews(status: str | None = None, app_id: str | None = None) -> list[dict[str, Any]]:
    return audit.list_cases(status, app_id)


class DecisionIn(BaseModel):
    decision: str
    note: str = ""


@router.post("/reviews/{case_id}/decide")
async def review_decide(case_id: str, body: DecisionIn) -> dict[str, Any]:
    try:
        return audit.decide_case(case_id, body.decision, body.note)
    except KeyError:
        raise HTTPException(404, "Case not found.") from None
    except ValueError as e:
        raise HTTPException(409, str(e)) from e


# ----------------------------------------------------------------- stats, reports
@router.get("/overview")
async def overview(days: int = Query(14, ge=1, le=90)) -> dict[str, Any]:
    return stats.overview(days)


@router.get("/reports/{app_id}", response_class=HTMLResponse)
async def report(app_id: str, date_from: str | None = Query(None, alias="from"), date_to: str | None = Query(None, alias="to")) -> HTMLResponse:
    html_ = reports.render_report(app_id, date_from, date_to)
    if html_ is None:
        raise HTTPException(404, "Application not found.")
    return HTMLResponse(html_)


# ----------------------------------------------------------------- seed, simulate
@router.post("/seed")
async def seed() -> dict[str, Any]:
    keys = seed_demo_apps()
    from scripts.seed import KEYS

    KEYS.write_text(json.dumps(keys, indent=2))
    return {"seeded": len(keys), "apps": [{"template": k, "app_id": v["app_id"], "name": v["name"], "key_prefix": v["key"][:12]} for k, v in keys.items()],
            "note": "Demo keys were saved to backend/.demo_keys.json for the traffic simulator."}


class SimIn(BaseModel):
    count: int = Field(100, ge=1, le=1000)
    days: float = Field(3, ge=0, le=30)


@router.post("/simulate")
async def simulate(body: SimIn, request: Request) -> dict[str, Any]:
    from scripts import simulate as sim
    from scripts.seed import KEYS

    if not KEYS.exists():
        await seed()
    keys = json.loads(KEYS.read_text())
    transport = httpx.ASGITransport(app=request.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://finguard.local", timeout=60) as c:
        probe = await c.post("/v1/messages", headers={"x-api-key": next(iter(keys.values()))["key"], "x-finguard-channel": "simulated"}, json={"model": "m", "max_tokens": 5, "messages": [{"role": "user", "content": "ping"}]})
        if probe.status_code == 401:  # keys file is stale (e.g. database was reset)
            await seed()
            keys = json.loads(KEYS.read_text())
        counts = await sim.run_simulation(c, keys, body.count, body.days)
    return {"sent": body.count, "actions": counts, "note": "Sent through the real gateway with channel=simulated (timestamps spread over the period and recorded as backdated)."}


# ----------------------------------------------------------------- evaluation
@router.post("/eval/run")
async def eval_run() -> dict[str, Any]:
    return await eval_runner.run_eval()


@router.get("/eval/latest")
async def eval_latest() -> dict[str, Any] | None:
    return eval_runner.latest_run()


# ----------------------------------------------------------------- demo
@router.get("/demo/scenarios")
async def demo_scenarios() -> list[dict[str, Any]]:
    return [{k: s[k] for k in ("scenario_id", "title", "surface", "use_case", "input", "without", "with", "role")} for s in demo.scenarios()]


@router.post("/demo/run/{scenario_id}")
async def demo_run(scenario_id: str) -> dict[str, Any]:
    sc = next((s for s in demo.scenarios() if s["scenario_id"] == scenario_id), None)
    if not sc:
        raise HTTPException(404, "Scenario not found.")
    if not registry.get_by_template(sc["use_case"]):
        seed_demo_apps()
    return await demo.run_scenario(sc)


@router.post("/demo/run-all")
async def demo_run_all() -> dict[str, Any]:
    if not registry.get_by_template("client_facing"):
        seed_demo_apps()
    results = [await demo.run_scenario(s) for s in demo.scenarios()]
    return {"results": results, "scorecard": demo.scorecard(results), "provider": providers.provider_name(), "model": "mock-model" if providers.is_mock() else get_settings().default_model}


@router.get("/demo/cache")
async def demo_cache() -> dict[str, Any]:
    res = demo.cached()
    return {"results": res, "scorecard": demo.scorecard(res) if res else None, "provider": providers.provider_name()}
