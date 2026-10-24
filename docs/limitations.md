# Limitations (read this)

## What each check really is
| Check | Type | Notes |
|---|---|---|
| IN-01 redaction | pattern + deterministic validators | regex with Luhn (cards) and mod-97 (IBAN); account numbers and DOB need context words; names/addresses are not detected unless Presidio is installed (optional, untested here) |
| IN-02 injection | pattern (+ optional model judge) | rule patterns after unicode folding, leetspeak, spaced letters and base64 decoding. Paraphrased attacks are missed (see the hard items in the evaluation report). The model judge is off by default, never runs in mock mode, and was **not exercised against a real model** |
| IN-03 topic | pattern | keyword lists per topic |
| IN-04 MNPI | pattern | non-public marker + event words, document ids, codenames. Paraphrases miss |
| IN-05 RBAC | deterministic | document ids, role clearance, app roles. Cannot map names to documents |
| OUT-01/02 | pattern | rewrite rules; advice detection needs a recommendation phrase plus a financial verb |
| OUT-03 grounding | deterministic | extracts %, money, dates and compares with the fictional approved data and the user's own figures; corrects when the sentence names a known product |
| OUT-04..05 | deterministic | citation ids, disclosures (idempotent) |
| OUT-06 vulnerability | pattern | first-person phrases only; subtle distress is missed |
| OUT-07..11 | pattern / deterministic | secrets, PII, fairness terms, tipping-off phrases, factor counting |
| Model judge | model (optional) | prompt in `backend/app/judge.py`; fails closed for high severity; can itself be prompt-injected, wrong, slow and costly |

## Honest caveats
- FinGuard only sees traffic routed through it. It cannot see public consumer apps (e.g. the claude.ai website).
- Streaming is buffered (output must be checked before release), so first-token latency equals full generation time plus checks.
- Regex and classifier checks miss cases; a clean audit record is not proof nothing risky happened.
- Regulation mappings are illustrative, not legal advice. Guardrails reduce risk and create evidence; they do not guarantee compliance. Humans stay accountable.
- The hash chain is a tamper-evidence demonstration, not a certified immutable store. Removing the newest records is only detectable if the head hash is stored elsewhere.
- Evaluation numbers come from a deterministic mock model and a label set written alongside the checks. They do not prove real-model performance.
- Binary documents (base64 PDFs/images) are not inspected. Simulated traffic may be backdated and is always labelled `simulated`.
- Not verified in the build environment: Docker/compose, a real Anthropic/OpenAI provider run, the optional model judge, Presidio, the Claude Code hooks inside a live Claude Code session, and the UI in a real browser.
