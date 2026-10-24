"""Anthropic Messages and OpenAI Chat Completions adapters: parse requests into checkable segments, format responses and SSE streams."""
from __future__ import annotations

import copy
import json
import time
import uuid
from collections.abc import Iterator
from typing import Any

from actions.base import Segment
from app.pipeline import Conversation


def _text_setter(container: Any, key: Any):
    def setter(new: str) -> None:
        container[key] = new
    return setter


class _Builder:
    def __init__(self) -> None:
        self.segs: list[Segment] = []
        self.setters: dict[int, Any] = {}

    def add(self, kind: str, text: str, msg: int, container: Any, key: Any) -> None:
        idx = len(self.segs)
        self.segs.append(Segment(kind, text, idx, msg))
        self.setters[idx] = _text_setter(container, key)


def parse_anthropic(body: dict[str, Any]) -> Conversation:
    payload = copy.deepcopy(body)
    b = _Builder()
    sysv = payload.get("system")
    if isinstance(sysv, str) and sysv:
        b.add("system", sysv, -1, payload, "system")
    elif isinstance(sysv, list):
        for blk in sysv:
            if isinstance(blk, dict) and blk.get("type") == "text":
                b.add("system", blk.get("text", ""), -1, blk, "text")
    for mi, m in enumerate(payload.get("messages", [])):
        role = "assistant" if m.get("role") == "assistant" else "user"
        c = m.get("content")
        if isinstance(c, str):
            b.add(role, c, mi, m, "content")
            continue
        for blk in c or []:
            if not isinstance(blk, dict):
                continue
            t = blk.get("type")
            if t == "text":
                b.add(role, blk.get("text", ""), mi, blk, "text")
            elif t == "tool_result":
                inner = blk.get("content")
                if isinstance(inner, str):
                    b.add("tool_result", inner, mi, blk, "content")
                elif isinstance(inner, list):
                    for ib in inner:
                        if isinstance(ib, dict) and ib.get("type") == "text":
                            b.add("tool_result", ib.get("text", ""), mi, ib, "text")
            elif t == "document":
                src = blk.get("source", {}) or {}
                if src.get("type") == "text":
                    b.add("document", src.get("data", ""), mi, src, "data")
                elif src.get("type") == "content":
                    for ib in src.get("content", []) if isinstance(src.get("content"), list) else []:
                        if isinstance(ib, dict) and ib.get("type") == "text":
                            b.add("document", ib.get("text", ""), mi, ib, "text")
                # base64 documents (e.g. PDF) cannot be inspected: documented limitation
    return Conversation("anthropic", str(payload.get("model", "")), int(payload.get("max_tokens", 1024) or 1024), b.segs, payload, b.setters, bool(payload.get("stream")))


def parse_openai(body: dict[str, Any]) -> Conversation:
    payload = copy.deepcopy(body)
    b = _Builder()
    for mi, m in enumerate(payload.get("messages", [])):
        r = m.get("role")
        kind = {"system": "system", "developer": "system", "assistant": "assistant", "tool": "tool_result", "function": "tool_result"}.get(r, "user")
        c = m.get("content")
        if isinstance(c, str):
            b.add(kind, c, -1 if kind == "system" else mi, m, "content")
        elif isinstance(c, list):
            for part in c:
                if isinstance(part, dict) and part.get("type") == "text":
                    b.add(kind, part.get("text", ""), -1 if kind == "system" else mi, part, "text")
    mt = payload.get("max_completion_tokens") or payload.get("max_tokens") or 1024
    return Conversation("openai", str(payload.get("model", "")), int(mt), b.segs, payload, b.setters, bool(payload.get("stream")))


def _tok(text: str) -> int:
    return max(1, len(text) // 4)


def anthropic_message(text: str, model: str, stop_reason: str = "end_turn", in_tok: int = 0, out_tok: int = 0) -> dict[str, Any]:
    return {"id": "msg_" + uuid.uuid4().hex[:24], "type": "message", "role": "assistant", "model": model, "content": [{"type": "text", "text": text}],
            "stop_reason": stop_reason, "stop_sequence": None, "usage": {"input_tokens": in_tok, "output_tokens": out_tok or _tok(text)}}


def openai_completion(text: str, model: str, finish: str = "stop", in_tok: int = 0, out_tok: int = 0) -> dict[str, Any]:
    out_tok = out_tok or _tok(text)
    return {"id": "chatcmpl-" + uuid.uuid4().hex[:24], "object": "chat.completion", "created": int(time.time()), "model": model,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": text, "refusal": None}, "finish_reason": "stop" if finish in ("end_turn", "stop") else finish}],
            "usage": {"prompt_tokens": in_tok, "completion_tokens": out_tok, "total_tokens": in_tok + out_tok}}


def _chunks(text: str, n: int = 24) -> list[str]:
    words = text.split(" ")
    out, cur = [], ""
    for w in words:
        if len(cur) + len(w) + 1 > n and cur:
            out.append(cur)
            cur = ""
        cur += (" " if cur or out else "") + w
    if cur:
        out.append(cur)
    return out or [""]


def _sse(event: str | None, data: Any) -> bytes:
    head = f"event: {event}\n" if event else ""
    return f"{head}data: {data if isinstance(data, str) else json.dumps(data)}\n\n".encode()


def anthropic_stream(text: str, model: str, stop_reason: str = "end_turn", in_tok: int = 0, out_tok: int = 0) -> Iterator[bytes]:
    """Emit an already-checked response as a valid Anthropic SSE stream."""
    mid = "msg_" + uuid.uuid4().hex[:24]
    yield _sse("message_start", {"type": "message_start", "message": {"id": mid, "type": "message", "role": "assistant", "model": model, "content": [],
                                                                         "stop_reason": None, "stop_sequence": None, "usage": {"input_tokens": in_tok, "output_tokens": 1}}})
    yield _sse("content_block_start", {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}})
    yield _sse("ping", {"type": "ping"})
    for ch in _chunks(text):
        yield _sse("content_block_delta", {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": ch}})
    yield _sse("content_block_stop", {"type": "content_block_stop", "index": 0})
    yield _sse("message_delta", {"type": "message_delta", "delta": {"stop_reason": stop_reason, "stop_sequence": None}, "usage": {"output_tokens": out_tok or _tok(text)}})
    yield _sse("message_stop", {"type": "message_stop"})


def openai_stream(text: str, model: str, finish: str = "stop", include_usage: bool = False, in_tok: int = 0, out_tok: int = 0) -> Iterator[bytes]:
    cid, created = "chatcmpl-" + uuid.uuid4().hex[:24], int(time.time())

    def chunk(delta: dict, fin: str | None = None, usage: dict | None = None) -> bytes:
        d = {"id": cid, "object": "chat.completion.chunk", "created": created, "model": model, "choices": [{"index": 0, "delta": delta, "finish_reason": fin}]}
        if usage is not None:
            d["usage"] = usage
        return _sse(None, d)

    yield chunk({"role": "assistant", "content": ""})
    for ch in _chunks(text):
        yield chunk({"content": ch})
    yield chunk({}, "stop" if finish in ("end_turn", "stop") else finish)
    if include_usage:
        o = out_tok or _tok(text)
        yield _sse(None, {"id": cid, "object": "chat.completion.chunk", "created": created, "model": model, "choices": [], "usage": {"prompt_tokens": in_tok, "completion_tokens": o, "total_tokens": in_tok + o}})
    yield b"data: [DONE]\n\n"


def anthropic_error(status: int, message: str) -> dict[str, Any]:
    et = {401: "authentication_error", 403: "permission_error", 404: "not_found_error", 429: "rate_limit_error"}.get(status, "api_error" if status >= 500 else "invalid_request_error")
    return {"type": "error", "error": {"type": et, "message": message}}


def openai_error(status: int, message: str) -> dict[str, Any]:
    et = {401: "authentication_error", 403: "permission_denied", 429: "rate_limit_exceeded"}.get(status, "server_error" if status >= 500 else "invalid_request_error")
    return {"error": {"message": message, "type": et, "param": None, "code": None}}
