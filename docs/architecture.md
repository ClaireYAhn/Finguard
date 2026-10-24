# Architecture

```
 SDK / Claude Code hook / agent ──► FinGuard (FastAPI)
   /v1/messages  /v1/chat/completions  /v1/guard/*        control panel (React) ──► /api/*
        │ app key → registry → policy pack@version
        ▼
   input rails ──► provider (mock | Anthropic | OpenAI) ──► output rails ──► audit (SHA-256 chain) ──► review queue
   (NeMo Guardrails Colang 1.0 flow → custom action → backend/actions/*)      reads ▲
```

- **Gateway** (`backend/gateway`): parses Anthropic and OpenAI request formats into typed segments (user, assistant, system, tool_result, document), so redaction writes back into the original structure and indirect injection in documents/tool results is scanned. Responses are returned in the caller's format; blocked requests get a normal-looking refusal plus `X-FinGuard-*` headers. Streaming is buffered: the full upstream answer is checked, then emitted as valid SSE.
- **Pipeline** (`backend/app/pipeline.py`): input stage (rules with stage input/dialogue/retrieval) → model → output stage → one audit record → review case if escalated. Precedence block > escalate > modify > allow.
- **Engines** (`backend/app/engines.py`): NeMo Guardrails 0.24.1 runs one input flow and one output flow (`backend/guardrails/config`); each `execute`s a registered action that runs all enabled checks. If NeMo fails, the same checks run natively and the failure is recorded in the trace (`engine: native`, note). Tool-stage checks ride on the input rail.
- **Checks** (`backend/actions`): one function per rule, returning rule_id, stage, status, severity, explanation, regulation refs, masked evidence, latency, check_type. A failing check never crashes a request: high severity fails closed, lower severity is skipped and shown in the trace.
- **Policy packs** (`backend/policies`): 10 YAML packs seeded as version 1 into SQLite; edits create versions; diff and rollback; each audit record stores the version used.
- **Audit** (`backend/audit`): SQLite, each record hashes the previous one; verify endpoint; head hash exposed. Decisions on review cases are new chained records.
- **Agent guard**: `/v1/guard/tool-call`, `/tool-result`, `/prompt` (used by the Claude Code prompt hook), approvals polling.
- **Evaluation** (`backend/eval`): runs labelled items through the real pipeline off and on, in an isolated in-memory database.

## Scope
FinGuard covers AI routes the firm controls (API gateway, Claude Code hooks, agent tool layer). It cannot filter public consumer apps such as the claude.ai website, because that traffic never passes through the firm.
