# FinGuard progress

Project lives in `finguard/` inside the pre-existing (unrelated) directory. Resume from the first unchecked item.
Backend venv: `cd backend && uv venv --python 3.11 .venv && uv pip install -r requirements.txt`.

- [x] Phase 1: NeMo spike (0.24.1, Colang 1.0 custom actions in input/output rails run without an LLM), scaffold
- [ ] Phase 2: backend core (providers, pipeline, engines, audit hash chain, registry, auth)
- [ ] Phase 3: checks + policy packs + unit tests + regulation-mapping generator
- [ ] Phase 4: gateway (both formats, streaming), agent guard, integrations
- [ ] Phase 5: review queue, fictional data, seed, simulator, evaluation suite
- [ ] Phase 6: frontend control panel + demo
- [ ] Phase 7: docker, docs, README, final verification
