"""Hash-chained audit log + review queue.

The chain demonstrates tamper evidence. It is NOT a certified immutable store: someone with write access to the file
can rewrite the whole chain, and deleting the newest records is only detectable if the head hash was stored elsewhere.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from actions.pii import find_pii, redact
from app.config import get_settings
from app.db import get_db

GENESIS = "0" * 64
HASHED_FIELDS = ["id", "ts", "app_id", "app_name", "user", "role", "channel", "original_input", "redacted_input", "raw_output", "final_output",
                 "rule_results", "final_action", "latency", "pack", "pack_version", "model", "engine", "extra"]
CHANNELS = {"gateway", "tool-call", "hook", "demo", "simulated", "review", "eval"}


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


def compute_hash(rec: dict[str, Any], prev: str) -> str:
    payload = json.dumps({k: rec.get(k) for k in HASHED_FIELDS}, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256((prev + payload).encode("utf-8")).hexdigest()


def storage_redact(text: str | None) -> str | None:
    """Redact sensitive data before storage unless FINGUARD_STORE_RAW is on."""
    if text is None or get_settings().store_raw:
        return text
    return redact(text, find_pii(text))


def head_hash() -> str:
    row = get_db().one("SELECT hash FROM audit ORDER BY seq DESC LIMIT 1")
    return row["hash"] if row else GENESIS


def write_audit(*, app_id: str | None, app_name: str, user: str, role: str, channel: str, original_input: str, redacted_input: str,
                raw_output: str | None, final_output: str | None, rule_results: list[dict], final_action: str, latency: dict,
                pack: str, pack_version: int, model: str, engine: str, extra: dict | None = None) -> dict[str, Any]:
    db = get_db()
    rec: dict[str, Any] = {
        "id": "aud_" + uuid.uuid4().hex[:16], "ts": now(), "app_id": app_id, "app_name": app_name, "user": user, "role": role, "channel": channel,
        "original_input": storage_redact(original_input), "redacted_input": storage_redact(redacted_input), "raw_output": storage_redact(raw_output),
        "final_output": storage_redact(final_output), "rule_results": json.dumps(rule_results, ensure_ascii=False, sort_keys=True),
        "final_action": final_action, "latency": json.dumps(latency, sort_keys=True), "pack": pack, "pack_version": pack_version, "model": model,
        "engine": engine, "extra": json.dumps(extra or {}, ensure_ascii=False, sort_keys=True),
    }
    with db.lock:
        db.execute("BEGIN IMMEDIATE")
        try:
            row = db.one("SELECT hash FROM audit ORDER BY seq DESC LIMIT 1")
            prev = row["hash"] if row else GENESIS
            rec["prev_hash"] = prev
            rec["hash"] = compute_hash(rec, prev)
            cols = list(rec)
            db.execute(f"INSERT INTO audit ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})", [rec[c] for c in cols])
            db.execute("COMMIT")
        except Exception:
            db.execute("ROLLBACK")
            raise
    return rec


def verify_chain() -> dict[str, Any]:
    prev, n = GENESIS, 0
    for row in get_db().query("SELECT * FROM audit ORDER BY seq ASC"):
        n += 1
        if row["prev_hash"] != prev:
            return {"ok": False, "count": n, "head_hash": head_hash(), "broken_at": row["seq"], "audit_id": row["id"],
                    "message": f"Record {row['id']} (seq {row['seq']}) does not link to the previous record: a record was removed, inserted or reordered."}
        if compute_hash(row, prev) != row["hash"]:
            return {"ok": False, "count": n, "head_hash": head_hash(), "broken_at": row["seq"], "audit_id": row["id"],
                    "message": f"Record {row['id']} (seq {row['seq']}) was modified after it was written: its hash no longer matches."}
        prev = row["hash"]
    return {"ok": True, "count": n, "head_hash": prev, "broken_at": None, "audit_id": None,
            "message": f"Chain intact: {n} record(s) verified. Store the head hash externally to also detect removal of the newest records."}


def _decode(row: dict[str, Any]) -> dict[str, Any]:
    r = dict(row)
    for k in ("rule_results", "latency", "extra"):
        try:
            r[k] = json.loads(r[k]) if r.get(k) else ([] if k == "rule_results" else {})
        except json.JSONDecodeError:
            r[k] = [] if k == "rule_results" else {}
    return r


def get_record(audit_id: str) -> dict[str, Any] | None:
    row = get_db().one("SELECT * FROM audit WHERE id=?", [audit_id])
    return _decode(row) if row else None


def query_records(*, app_id: str | None = None, action: str | None = None, rule: str | None = None, severity: str | None = None,
                  channel: str | None = None, date_from: str | None = None, date_to: str | None = None, q: str | None = None,
                  limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
    where, params = ["1=1"], []
    if app_id:
        where.append("app_id=?"); params.append(app_id)
    if action:
        where.append("final_action=?"); params.append(action)
    if channel:
        where.append("channel=?"); params.append(channel)
    if date_from:
        where.append("ts>=?"); params.append(date_from)
    if date_to:
        where.append("ts<=?"); params.append(date_to if len(date_to) > 10 else date_to + "T23:59:59.999")
    if q:
        where.append("(redacted_input LIKE ? OR final_output LIKE ?)"); params += [f"%{q}%", f"%{q}%"]
    if rule:
        where.append("rule_results LIKE ?"); params.append(f'%"rule_id": "{rule}"%')
    sql = f"SELECT * FROM audit WHERE {' AND '.join(where)} ORDER BY seq DESC LIMIT ? OFFSET ?"
    rows = [_decode(r) for r in get_db().query(sql, [*params, limit if not severity else 5000, offset])]
    if rule:  # rule filter only counts rules that actually fired
        rows = [r for r in rows if any(x["rule_id"] == rule and x["status"] != "pass" for x in r["rule_results"])]
    if severity:
        rows = [r for r in rows if any(x["severity"] == severity and x["status"] != "pass" for x in r["rule_results"])][:limit]
    return rows


def export_csv(rows: list[dict[str, Any]]) -> str:
    buf = io.StringIO()
    cols = ["id", "ts", "app_name", "user", "role", "channel", "final_action", "rules_fired", "pack", "pack_version", "model", "engine", "redacted_input", "final_output", "hash"]
    w = csv.writer(buf)
    w.writerow(cols)
    for r in rows:
        fired = ";".join(x["rule_id"] for x in r["rule_results"] if x["status"] != "pass")
        w.writerow([fired if c == "rules_fired" else r.get(c, "") for c in cols])
    return buf.getvalue()


# ----------------------------------------------------------------- review queue
def create_case(*, audit_id: str, app_id: str | None, app_name: str, kind: str, reason: str, rule_ids: list[str], severity: str = "high",
                payload: dict | None = None) -> dict[str, Any]:
    cid = "case_" + uuid.uuid4().hex[:12]
    get_db().execute(
        "INSERT INTO reviews (id,audit_id,app_id,app_name,kind,status,reason,rule_ids,created_at,payload,severity) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        [cid, audit_id, app_id, app_name, kind, "open", reason, json.dumps(rule_ids), now(), json.dumps(payload or {}), severity])
    return get_case(cid)  # type: ignore[return-value]


def _case(row: dict[str, Any]) -> dict[str, Any]:
    r = dict(row)
    r["rule_ids"] = json.loads(r["rule_ids"] or "[]")
    r["payload"] = json.loads(r["payload"] or "{}")
    return r


def get_case(cid: str) -> dict[str, Any] | None:
    row = get_db().one("SELECT * FROM reviews WHERE id=?", [cid])
    return _case(row) if row else None


def list_cases(status: str | None = None, app_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
    where, params = ["1=1"], []
    if status:
        where.append("status=?"); params.append(status)
    if app_id:
        where.append("app_id=?"); params.append(app_id)
    return [_case(r) for r in get_db().query(f"SELECT * FROM reviews WHERE {' AND '.join(where)} ORDER BY created_at DESC LIMIT ?", [*params, limit])]


def decide_case(cid: str, decision: str, note: str, reviewer: str = "admin") -> dict[str, Any]:
    case = get_case(cid)
    if not case:
        raise KeyError(cid)
    if case["status"] != "open":
        raise ValueError(f"Case already {case['status']}")
    if decision not in ("approved", "rejected"):
        raise ValueError("decision must be approved or rejected")
    get_db().execute("UPDATE reviews SET status=?, reviewer_note=?, decided_at=? WHERE id=?", [decision, note, now(), cid])
    write_audit(app_id=case["app_id"], app_name=case["app_name"], user=reviewer, role="reviewer", channel="review",
                original_input=f"review of {cid} ({case['kind']})", redacted_input="", raw_output=None, final_output=f"{decision}: {note}",
                rule_results=[], final_action=f"review_{decision}", latency={}, pack="", pack_version=0, model="", engine="n/a",
                extra={"case_id": cid, "audit_id_reviewed": case["audit_id"], "kind": case["kind"], "note": note})
    return get_case(cid)  # type: ignore[return-value]
