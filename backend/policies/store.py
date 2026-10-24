"""Versioned policy packs. YAML files seed version 1; edits create new versions in SQLite."""
from __future__ import annotations

import difflib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, field_validator

from actions.base import CHECKS, RegRef, RuleConfig
from app.db import get_db

PACK_DIR = Path(__file__).resolve().parent / "packs"
_cache: dict[tuple, dict[str, Any]] = {}


class RuleModel(BaseModel):
    id: str
    name: str = ""
    description: str = ""
    stage: str
    enabled: bool = True
    severity: Literal["low", "medium", "high"] = "medium"
    action: Literal["allow", "modify", "block", "escalate", "log"] = "log"
    thresholds: dict[str, Any] = Field(default_factory=dict)
    regulations: list[dict[str, str]] = Field(default_factory=list)

    @field_validator("id")
    @classmethod
    def known(cls, v: str) -> str:
        if v not in CHECKS:
            raise ValueError(f"unknown rule id {v}")
        return v


class PackModel(BaseModel):
    pack: str
    title: str
    version: int = 1
    risk_tier: str = "limited"
    regulation_note: str = "All mappings are illustrative, not legal advice."
    settings: dict[str, Any] = Field(default_factory=dict)
    rules: list[RuleModel]


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def seed_packs() -> int:
    """Insert v1 of every YAML pack that has no stored version. Returns number inserted."""
    n = 0
    for f in sorted(PACK_DIR.glob("*.yaml")):
        data = yaml.safe_load(f.read_text())
        if not get_db().one("SELECT 1 FROM policy_versions WHERE pack=?", [data["pack"]]):
            PackModel.model_validate(data)
            get_db().execute("INSERT INTO policy_versions (pack,version,content,created_at,author,note) VALUES (?,?,?,?,?,?)",
                             [data["pack"], 1, json.dumps(data), _now(), "system", "Initial version from YAML"])
            n += 1
    return n


def list_packs() -> list[dict[str, Any]]:
    out = []
    for r in get_db().query("SELECT pack, MAX(version) AS version FROM policy_versions GROUP BY pack ORDER BY pack"):
        p = get_pack(r["pack"])
        if p:
            out.append({"pack": r["pack"], "title": p["title"], "version": r["version"], "risk_tier": p.get("risk_tier"),
                        "rules_enabled": sum(1 for x in p["rules"] if x["enabled"]), "rules_total": len(p["rules"])})
    return out


def get_pack(name: str, version: int | None = None) -> dict[str, Any] | None:
    if version is None:
        row = get_db().one("SELECT MAX(version) AS v FROM policy_versions WHERE pack=?", [name])
        if not row or row["v"] is None:
            return None
        version = int(row["v"])
    key = (id(get_db()), name, version)
    if key not in _cache:
        row = get_db().one("SELECT content FROM policy_versions WHERE pack=? AND version=?", [name, version])
        if not row:
            return None
        data = json.loads(row["content"])
        data["version"] = version
        _cache[key] = data
    return json.loads(json.dumps(_cache[key]))


def clear_cache() -> None:
    _cache.clear()


def save_new_version(name: str, content: dict[str, Any], author: str = "admin", note: str = "") -> dict[str, Any]:
    cur = get_pack(name)
    if cur is None:
        raise KeyError(name)
    content = {**content, "pack": name}
    PackModel.model_validate(content)
    new_v = cur["version"] + 1
    content["version"] = new_v
    get_db().execute("INSERT INTO policy_versions (pack,version,content,created_at,author,note) VALUES (?,?,?,?,?,?)",
                     [name, new_v, json.dumps(content), _now(), author, note])
    return get_pack(name, new_v)  # type: ignore[return-value]


def history(name: str) -> list[dict[str, Any]]:
    return get_db().query("SELECT version, created_at, author, note FROM policy_versions WHERE pack=? ORDER BY version DESC", [name])


def rollback(name: str, version: int, author: str = "admin") -> dict[str, Any]:
    old = get_pack(name, version)
    if old is None:
        raise KeyError(f"{name} v{version}")
    old.pop("version", None)
    return save_new_version(name, old, author, f"Rollback to version {version}")


def diff(name: str, a: int, b: int) -> dict[str, Any]:
    pa, pb = get_pack(name, a), get_pack(name, b)
    if pa is None or pb is None:
        raise KeyError(name)
    ya, yb = (yaml.safe_dump({k: v for k, v in p.items() if k != "version"}, sort_keys=False, width=100) for p in (pa, pb))
    text = "".join(difflib.unified_diff(ya.splitlines(True), yb.splitlines(True), f"{name} v{a}", f"{name} v{b}"))
    ra, rb = {r["id"]: r for r in pa["rules"]}, {r["id"]: r for r in pb["rules"]}
    changes = []
    for rid in sorted(set(ra) | set(rb)):
        if ra.get(rid) != rb.get(rid):
            fields = [k for k in set(ra.get(rid, {})) | set(rb.get(rid, {})) if ra.get(rid, {}).get(k) != rb.get(rid, {}).get(k)]
            changes.append({"rule_id": rid, "fields": sorted(fields),
                            "before": {k: ra.get(rid, {}).get(k) for k in fields}, "after": {k: rb.get(rid, {}).get(k) for k in fields}})
    if pa.get("settings") != pb.get("settings"):
        changes.append({"rule_id": "settings", "fields": ["settings"], "before": pa.get("settings"), "after": pb.get("settings")})
    return {"pack": name, "from": a, "to": b, "unified": text, "changes": changes}


def rule_configs(pack: dict[str, Any]) -> list[RuleConfig]:
    out = []
    for r in pack["rules"]:
        out.append(RuleConfig(id=r["id"], name=r.get("name", ""), description=r.get("description", ""), stage=r["stage"], enabled=r["enabled"],
                              severity=r["severity"], action=r["action"], thresholds=r.get("thresholds", {}),
                              regulations=[RegRef(**x) for x in r.get("regulations", [])]))
    return out
