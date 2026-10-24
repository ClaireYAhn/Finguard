# Decisions

## D1. Location
The working directory already contained an unrelated browser extension (background.js, manifest.json...), and was not a git repo. To avoid mixing, FinGuard lives in `finguard/` with its own git repository. The extension files are untouched.

## D1b. Final location
Mid-build, `~/Downloads/recreg-extension` (including the `finguard/` subfolder) was moved to the Trash and replaced by a fresh copy of the extension by a process outside this session (the folder reappeared at the same minute as `~/Downloads/recreg-extension.zip` was rewritten). Nothing in FinGuard's own commands touches that path. The complete project was recovered from `~/.Trash/recreg-extension/finguard` (git history intact) and now lives at `~/Projects/finguard`. The Trash original was left untouched.

## D2. NeMo Guardrails version and Colang
Installed: `nemoguardrails==0.24.1` (latest on PyPI at build time), Python 3.11. Colang **1.0** (`colang_version: "1.0"`).
Spike result (verified by running it, see `backend/tests/test_nemo_spike.py`): an `LLMRails` built from a config with **no `models:` section** can run
`generate_async(messages, options={"rails": ["input"]})` and `options={"rails": ["output"]}`; the flows `execute` custom Python actions
and `stop` after a `bot refuse` response. So FinGuard uses NeMo purely as the rail executor and does not need NeMo to call an LLM
(the model call is made by FinGuard's provider layer so streaming/format handling stays under our control).
Design: one NeMo input flow and one output flow each `execute` a FinGuard action (`finguard_input_rails`, `finguard_output_rails`) that runs the
custom check modules in `backend/actions`. Full per-rule results are passed back through a context variable (NeMo only sees allow/stop).
`engine` is recorded in every trace as `nemo` or `native`. If NeMo fails to load/execute, the same check functions are called directly
(`native`) and the trace says so (with the NeMo error) - nothing is silently skipped.

## D3. Rule semantics
Final action precedence: block > escalate > modify > allow. `log` action records the finding without changing output.
`escalate` withholds the content (safe holding message) and opens a review case. Vulnerability (OUT-06) releases a supportive replacement and also opens a case.

## D4. Check statuses
Check status in {pass, modified, blocked, escalated}. A check that raises: severity high -> fail closed (blocked, evidence "check error"); lower severity -> skipped, shown in trace as `pass` with `error` populated.

## D5. Storage
SQLite via sqlite3 (stdlib), WAL mode, one process. Policy packs ship as YAML in `backend/policies/packs/` and are copied into a `policy_versions` table on first start; edits create new versions in the DB.

## D6. Auth
Admin: single password env var, HMAC-signed session cookie (HttpOnly, SameSite=Lax). App keys: `fg_live_...`, SHA-256 hashed at rest, shown once.

## D7. Providers
Plain `httpx` calls to Anthropic Messages and OpenAI Chat Completions (no vendor SDKs on the server). Mock provider is deterministic and deliberately produces risky output.

## D8. Evaluation honesty
Violations are measured by per-item independent "harm probes" (regex/strings in the dataset, e.g. the raw card number or the injected canary) applied to what reached the model and what was delivered, not by re-running the guard rules.
