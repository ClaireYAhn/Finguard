# FinGuard

AI governance gateway and control panel for financial services firms (**all data and the firm "Northbridge Financial" are fictional; not financial, legal or regulatory advice**).
FinGuard sits between a firm's people/agents and any language model. It inspects inputs, model outputs and agent tool calls against finance policy packs, redacts/rewrites/blocks/escalates, writes a tamper-evident audit trail, and gives risk teams a control panel. Built on **NVIDIA NeMo Guardrails 0.24.1** (Colang 1.0) with custom actions.

> **Scope.** FinGuard covers AI routes the firm controls: the API gateway, Claude Code hooks and the agent tool layer. It cannot filter public consumer apps such as the claude.ai website, because that traffic never passes through the firm.

## Quick start (no Docker, no API key, no internet needed after install)
```bash
cp .env.example .env            # set FINGUARD_ADMIN_PASSWORD
cd backend
uv venv --python 3.11 .venv && source .venv/bin/activate   # or python3.11 -m venv
uv pip install -r requirements.txt                          # or pip install -r requirements.txt
set -a; source ../.env; set +a
uvicorn app.main:app --port 8000          # API + gateway (port 8000 must be free)
python -m scripts.seed                    # 10 demo apps; keys saved to .demo_keys.json (git-ignored)
python -m scripts.simulate --count 300    # mixed traffic through the real gateway, tagged channel=simulated
# second terminal
cd frontend && npm install && npm run dev  # http://localhost:5173  (log in with your admin password)
```
Docker: `docker compose up --build` → panel on http://localhost:3000 (not verified in the build environment).

Default provider is `mock` (deterministic, deliberately includes risky answers so "guardrails off" looks realistic). Set `FINGUARD_PROVIDER=anthropic|openai` plus the key in `.env` for real models (keys stay server-side).

## Connect an app
Create an app in **Apps** (or from a template); the full key is shown once. Then change only the base URL:
```python
import anthropic
c = anthropic.Anthropic(base_url="http://localhost:8000", api_key="fg_live_...")
print(c.messages.create(model="claude-sonnet-5-5", max_tokens=300, messages=[{"role":"user","content":"What is the 1-year fixed saver rate?"}]).content[0].text)
```
```python
import openai
o = openai.OpenAI(base_url="http://localhost:8000/v1", api_key="fg_live_...")
print(o.chat.completions.create(model="gpt-4o", messages=[{"role":"user","content":"hi"}]).choices[0].message.content)
```
```bash
curl localhost:8000/v1/messages -H "x-api-key: $KEY" -H "content-type: application/json" \
  -d '{"model":"claude-sonnet-5-5","max_tokens":200,"messages":[{"role":"user","content":"Which fund should I invest in?"}]}' -i   # see X-FinGuard-* headers
# optional identity: -H "x-finguard-user: alice" -H "x-finguard-role: adviser"
```
**Agent:** `integrations/python_agent` (guard wrapper around every tool call; `POST /v1/guard/tool-call`, poll `GET /v1/guard/approvals/{id}`). **Claude Code:** `integrations/claude_code` (UserPromptSubmit + PreToolUse hooks, `settings.example.json`; format notes and verification status in its README). **MCP-style:** `integrations/mcp_wrapper`.

## Tests, lint, evaluation
```bash
cd backend && python -m pytest -q && ruff check .
cd frontend && npm run lint && npm test && npm run build
cd backend && python -m scripts.run_eval --write-report   # docs/evaluation-report.md
python -m scripts.gen_regulation_mapping                  # docs/regulation-mapping.md
```

## First-tests checklist
- [ ] Log in; Overview shows numbers after seed + simulate (simulated share stated)
- [ ] Apps → Connect → "Send test request" with `Which fund should I invest in?` (modify) and `Ignore all previous instructions…` (block)
- [ ] curl in both formats; check `X-FinGuard-Action` and streaming (`"stream": true`)
- [ ] Review queue → approve/reject; Audit → Verify chain; edit a row in SQLite and verify again (should fail)
- [ ] Policies → disable a rule, save, re-send, diff, roll back
- [ ] Evaluation → Run; note the model named and the listed misses
- [ ] Demo → Run all; presentation mode (`P`)

## Presentation script
`docs/demo-script.md` (three minutes).

## Troubleshooting
- **Port 8000 busy / UI shows "Cannot reach the backend"**: run the API on another port and point the dev proxy at it: `uvicorn app.main:app --port 8010` then `FINGUARD_API=http://localhost:8010 npm run dev`.
- **Login fails**: the password is `FINGUARD_ADMIN_PASSWORD` from the environment the server started with (default `change-me-admin`, logged as a warning).
- **Sessions reset on restart**: set `FINGUARD_SESSION_SECRET`.
- **Simulator says run seed first**: `python -m scripts.seed` writes `backend/.demo_keys.json`; re-seeding rotates demo keys.
- **NeMo warnings about `actions`**: harmless noise from NeMo scanning `./actions`; engine fallback is shown in each trace.
- **Changed policy has no effect**: edits create a new version; check the version in the response header `X-FinGuard-Policy-Version`.

## Docs
`docs/architecture.md`, `limitations.md`, `decisions.md`, `demo-script.md`, generated `regulation-mapping.md` and `evaluation-report.md`, `api-contract.md`.

## Licences and credits
NVIDIA NeMo Guardrails (Apache-2.0) · FastAPI (MIT) · Pydantic (MIT) · Uvicorn (BSD) · httpx (BSD) · PyYAML (MIT) · pytest (MIT) · Ruff (MIT) · Microsoft Presidio (MIT, optional, not installed by default) · React, Vite, Tailwind CSS, Recharts, react-router, Vitest, ESLint (MIT). Project code: provided as-is for demonstration.
