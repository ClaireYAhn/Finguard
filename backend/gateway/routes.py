"""POST /v1/messages (Anthropic format) and POST /v1/chat/completions (OpenAI format)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from app import providers
from app.auth import AuthError, authenticate_app
from app.pipeline import Conversation, GovernResult, UpstreamError, govern
from audit.store import CHANNELS

from . import adapters

router = APIRouter()


def resolve_identity(request: Request, app: dict[str, Any]) -> tuple[str, str, str]:
    user = request.headers.get("x-finguard-user") or "anonymous"
    role = request.headers.get("x-finguard-role") or app.get("default_role") or "staff"
    channel = (request.headers.get("x-finguard-channel") or "gateway").lower()
    if channel not in CHANNELS - {"review", "eval", "demo"} | {"gateway"}:
        channel = "gateway"
    return user, role, channel


async def _handle(request: Request, fmt: str) -> Any:
    err = adapters.anthropic_error if fmt == "anthropic" else adapters.openai_error
    try:
        app = authenticate_app(request)
    except AuthError as e:
        return JSONResponse(err(e.status, str(e)), status_code=e.status)
    try:
        body = await request.json()
        if not isinstance(body, dict) or not isinstance(body.get("messages"), list) or not body["messages"]:
            raise ValueError("'messages' must be a non-empty list")
        conv: Conversation = adapters.parse_anthropic(body) if fmt == "anthropic" else adapters.parse_openai(body)
        if not any(s.kind == "user" for s in conv.segments):
            raise ValueError("no user message found")
    except Exception as e:  # noqa: BLE001
        return JSONResponse(err(400, f"Invalid request body: {e}"), status_code=400)
    user, role, channel = resolve_identity(request, app)
    try:
        res: GovernResult = await govern(app=app, conv=conv, role=role, user=user, channel=channel)
    except UpstreamError as e:
        return JSONResponse(err(e.status, str(e)), status_code=e.status)
    model = res.model or conv.model or "finguard"
    in_tok = res.provider.input_tokens if res.provider else 0
    out_tok = res.provider.output_tokens if res.provider else 0
    headers = res.headers()
    if conv.stream:
        # Streaming is buffered on purpose: the full upstream answer is checked before any byte is released to the caller.
        include_usage = bool((body.get("stream_options") or {}).get("include_usage"))
        gen = (adapters.anthropic_stream(res.final_text, model, res.stop_reason, in_tok, out_tok) if fmt == "anthropic"
               else adapters.openai_stream(res.final_text, model, res.stop_reason, include_usage, in_tok, out_tok))
        return StreamingResponse(gen, media_type="text/event-stream", headers={**headers, "Cache-Control": "no-cache", "X-FinGuard-Buffered": "true"})
    payload = (adapters.anthropic_message(res.final_text, model, res.stop_reason, in_tok, out_tok) if fmt == "anthropic"
               else adapters.openai_completion(res.final_text, model, res.stop_reason, in_tok, out_tok))
    return JSONResponse(payload, headers=headers)


@router.post("/v1/messages")
async def messages(request: Request) -> Any:
    return await _handle(request, "anthropic")


@router.post("/v1/chat/completions")
async def chat_completions(request: Request) -> Any:
    return await _handle(request, "openai")


@router.get("/v1/models")
async def models() -> dict[str, Any]:
    return {"object": "list", "data": [{"id": "mock-model" if providers.is_mock() else providers.default_model_for("anthropic"), "object": "model"}]}
