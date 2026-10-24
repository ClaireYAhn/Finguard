"""Cached access to fictional reference data."""
from __future__ import annotations

from functools import lru_cache
from typing import Any

from .base import load_json


@lru_cache(maxsize=1)
def products() -> dict[str, Any]:
    return load_json("products.json")


@lru_cache(maxsize=1)
def documents() -> dict[str, dict[str, Any]]:
    d = load_json("documents.json")
    return {x["id"]: x for x in d["documents"]}


@lru_cache(maxsize=1)
def levels() -> dict[str, int]:
    return load_json("documents.json")["classification_levels"]


@lru_cache(maxsize=1)
def roles() -> dict[str, Any]:
    return load_json("roles.json")["roles"]


@lru_cache(maxsize=1)
def clients() -> list[dict[str, Any]]:
    return load_json("clients.json")["clients"]


def clearance(role: str) -> int:
    return int(roles().get(role, {"clearance": 0})["clearance"])


def can_access(role: str, doc: dict[str, Any]) -> bool:
    allowed = doc.get("allowed_roles")
    if allowed is not None and role in allowed:
        return True
    if allowed is not None and doc["classification"] in ("restricted", "mnpi"):
        return False
    return clearance(role) >= levels()[doc["classification"]]
