"""Use-case (app) registry. Only a SHA-256 hash of each app key is stored; the full key is shown once."""
from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from datetime import UTC, datetime
from typing import Any

from app.db import get_db
from registry.templates import TEMPLATES

KEY_PREFIX = "fg_live_"
JSON_FIELDS = ("data_classes", "allowed_roles", "tool_policy")
EDITABLE = {"name", "owner", "business_unit", "description", "risk_tier", "eu_ai_act_note", "model", "data_classes", "policy_pack",
            "allowed_roles", "default_role", "tool_policy", "enabled"}


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def new_key() -> str:
    return KEY_PREFIX + secrets.token_urlsafe(32)


def _dec(row: dict[str, Any]) -> dict[str, Any]:
    r = dict(row)
    for f in JSON_FIELDS:
        r[f] = json.loads(r[f]) if r.get(f) else ([] if f != "tool_policy" else {})
    r["enabled"] = bool(r["enabled"])
    r["is_demo"] = bool(r.get("is_demo"))
    r.pop("key_hash", None)
    return r


def create_app(*, name: str, owner: str = "", business_unit: str = "", description: str = "", risk_tier: str = "limited", eu_ai_act_note: str = "",
               model: str = "claude-sonnet-5-5", data_classes: list[str] | None = None, policy_pack: str = "internal_staff",
               allowed_roles: list[str] | None = None, default_role: str = "staff", tool_policy: dict | None = None,
               template: str | None = None, is_demo: bool = False) -> tuple[dict[str, Any], str]:
    """Create an app. Returns (app, raw_key); the raw key is not retrievable later."""
    key = new_key()
    aid = "app_" + uuid.uuid4().hex[:10]
    get_db().execute(
        "INSERT INTO apps (id,name,owner,business_unit,description,risk_tier,eu_ai_act_note,model,data_classes,policy_pack,allowed_roles,default_role,tool_policy,enabled,created_at,key_prefix,key_hash,template,is_demo)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,1,?,?,?,?,?)",
        [aid, name, owner, business_unit, description, risk_tier, eu_ai_act_note, model, json.dumps(data_classes or []), policy_pack,
         json.dumps(allowed_roles or []), default_role, json.dumps(tool_policy or {}), datetime.now(UTC).isoformat(timespec="seconds"),
         key[:12], hash_key(key), template, int(is_demo)])
    return get_app(aid), key  # type: ignore[return-value]


def create_from_template(template: str, *, name: str | None = None, owner: str = "", business_unit: str = "", is_demo: bool = False) -> tuple[dict[str, Any], str]:
    t = TEMPLATES[template]
    return create_app(name=name or t["name"], owner=owner, business_unit=business_unit, description=t["description"], risk_tier=t["risk_tier"],
                      eu_ai_act_note=t["eu_ai_act_note"], model=t["model"], data_classes=t["data_classes"], policy_pack=template,
                      allowed_roles=t["allowed_roles"], default_role=t["default_role"], tool_policy=t["tool_policy"], template=template, is_demo=is_demo)


def get_app(app_id: str) -> dict[str, Any] | None:
    row = get_db().one("SELECT * FROM apps WHERE id=?", [app_id])
    return _dec(row) if row else None


def get_by_key(key: str) -> dict[str, Any] | None:
    row = get_db().one("SELECT * FROM apps WHERE key_hash=?", [hash_key(key)])
    return _dec(row) if row else None


def get_by_template(template: str) -> dict[str, Any] | None:
    row = get_db().one("SELECT * FROM apps WHERE template=? ORDER BY created_at LIMIT 1", [template])
    return _dec(row) if row else None


def list_apps() -> list[dict[str, Any]]:
    return [_dec(r) for r in get_db().query("SELECT * FROM apps ORDER BY created_at, name")]


def update_app(app_id: str, fields: dict[str, Any]) -> dict[str, Any] | None:
    sets, params = [], []
    for k, v in fields.items():
        if k not in EDITABLE:
            continue
        sets.append(f"{k}=?")
        params.append(json.dumps(v) if k in JSON_FIELDS else (int(v) if k == "enabled" else v))
    if sets:
        get_db().execute(f"UPDATE apps SET {','.join(sets)} WHERE id=?", [*params, app_id])
    return get_app(app_id)


def rotate_key(app_id: str) -> tuple[dict[str, Any], str] | None:
    if not get_app(app_id):
        return None
    key = new_key()
    get_db().execute("UPDATE apps SET key_prefix=?, key_hash=? WHERE id=?", [key[:12], hash_key(key), app_id])
    return get_app(app_id), key  # type: ignore[return-value]


def delete_app(app_id: str) -> bool:
    cur = get_db().execute("DELETE FROM apps WHERE id=?", [app_id])
    return cur.rowcount > 0
