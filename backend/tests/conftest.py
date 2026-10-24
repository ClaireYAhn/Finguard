from __future__ import annotations

import os
import tempfile

import pytest

os.environ.setdefault("FINGUARD_PROVIDER", "mock")
os.environ["FINGUARD_ADMIN_PASSWORD"] = "test-password"
os.environ["FINGUARD_SESSION_SECRET"] = "test-secret"
os.environ["FINGUARD_STORE_RAW"] = "false"

import actions  # noqa: E402,F401
from actions.base import Ctx, RuleConfig, Segment, run_check  # noqa: E402
from app.config import reload_settings  # noqa: E402
from app.db import reset_db  # noqa: E402
from policies import store as policies  # noqa: E402
from registry import store as registry  # noqa: E402
from registry.templates import TEMPLATES  # noqa: E402

reload_settings()


@pytest.fixture()
def db():
    d = tempfile.mkdtemp()
    database = reset_db(os.path.join(d, "t.db"))
    policies.clear_cache()
    policies.seed_packs()
    return database


@pytest.fixture()
def apps(db):
    out = {}
    for key in TEMPLATES:
        app, raw = registry.create_from_template(key, is_demo=True)
        out[key] = {"app": app, "key": raw}
    return out


@pytest.fixture()
def client(apps):
    from fastapi.testclient import TestClient

    from app.main import create_app

    with TestClient(create_app()) as c:
        c.apps = apps  # type: ignore[attr-defined]
        yield c


@pytest.fixture()
def admin(client):
    r = client.post("/api/auth/login", json={"password": "test-password"})
    assert r.status_code == 200
    return client


def rule(rid: str, action: str = "modify", severity: str = "high", stage: str | None = None, **thr) -> RuleConfig:
    st = stage or ("input" if rid.startswith("IN") else "output" if rid.startswith("OUT") else "tool")
    return RuleConfig(id=rid, stage=st, severity=severity, action=action, thresholds=thr)


def run_input(rid: str, text: str, action: str = "modify", role: str = "client", app: dict | None = None, settings: dict | None = None, segments=None, **thr):
    ctx = Ctx(text=text, user_input=text, segments=segments or [Segment("user", text, 0)], role=role, app=app or {}, settings=settings or {})
    return run_check(rule(rid, action, **thr), ctx), ctx


def run_output(rid: str, output: str, user: str = "hello", action: str = "modify", role: str = "client", settings: dict | None = None, segments=None, **thr):
    segs = segments or [Segment("user", user, 0)]
    ctx = Ctx(text=output, output=output, user_input=user, segments=segs, role=role, settings=settings or {})
    return run_check(rule(rid, action, **thr), ctx)
