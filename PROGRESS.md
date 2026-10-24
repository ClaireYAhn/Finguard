# FinGuard progress

Project lives in `finguard/` inside a pre-existing, unrelated directory (see docs/decisions.md D1). Resume from the first unchecked item.
Backend venv: `cd backend && uv venv --python 3.11 .venv && uv pip install -r requirements.txt`.

- [x] Phase 1: NeMo spike (0.24.1, Colang 1.0 custom actions in input/output rails run without an LLM), scaffold
- [x] Phase 2: backend core modules (providers, pipeline, engines nemo+native, audit hash chain, registry, auth, policy store)
- [~] Phase 3: all 16 checks + tool checks + 10 YAML packs + eval harness/dataset DONE. TODO: unit tests, regulation-mapping generator
- [ ] Phase 4: FastAPI wiring (main.py, admin routes, guard routes), gateway routes written (untested), integrations folder
- [ ] Phase 5: review queue API, seed/simulator scripts, demo scenarios, eval API + report generator
- [ ] Phase 6: frontend control panel + demo
- [ ] Phase 7: docker, docs, README, final verification
