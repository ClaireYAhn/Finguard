"""Model providers: mock (offline, deterministic, deliberately risky), Anthropic and OpenAI over plain httpx.

API keys are read from server environment variables only.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import httpx

from actions.pii import find_pii

from .config import get_settings


@dataclass
class ProviderRequest:
    model: str
    system: str
    messages: list[dict[str, str]]  # flattened {"role","content"}
    max_tokens: int = 1024
    raw_payload: dict[str, Any] | None = None  # original provider-format body (redacted), used for real providers
    fmt: str = "anthropic"
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderResponse:
    text: str
    model: str
    stop_reason: str = "end_turn"
    input_tokens: int = 0
    output_tokens: int = 0
    provider: str = "mock"


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


# --------------------------------------------------------------------------- mock
_FACT_ANSWERS = [
    (r"easy access", "The Northbridge Easy Access Saver pays 3.10% AER (variable), with a minimum deposit of £1."),
    (r"(1[- ]year|one[- ]year|fixed saver)", "The Northbridge 1-Year Fixed Saver pays 4.60% AER fixed for 1 year, with a minimum deposit of £500."),
    (r"3[- ]year", "The Northbridge 3-Year Fixed Saver pays 4.15% AER fixed for 3 years."),
    (r"(isa).*(fee|charge|cost)|(fee|charge|cost).*(isa)|platform fee", "The Northbridge Investment ISA has a platform fee of 0.45% a year and a dealing fee of £3.00 per trade. The annual ISA allowance is £20,000."),
    (r"overdraft", "The Everyday Current Account has an arranged overdraft rate of 35.0% EAR (variable) and no monthly fee."),
    (r"global equity", "The Northbridge Global Equity Fund returned 8.4% over 1 year to 31 December 2025, with an ongoing charge of 0.22%. Past performance is not a guide to future returns."),
    (r"uk income", "The Northbridge UK Income Fund has a distribution yield of 3.8% and an ongoing charge of 0.30%."),
    (r"cautious bond", "The Northbridge Cautious Bond Fund returned 2.9% over 1 year to 31 December 2025, with an ongoing charge of 0.18%."),
    (r"branch|opening hours", "Our branches are open 9am to 5pm on weekdays."),
]


def _expand(text: str) -> str:
    import base64

    from actions.textutil import normalise

    base = normalise(text)
    parts = [base, base.translate(str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s"}))]
    for m in re.finditer(r"[A-Za-z0-9+/]{24,}={0,2}", text):
        try:
            parts.append(normalise(base64.b64decode(m.group() + "=" * (-len(m.group()) % 4)).decode("utf-8")))
        except Exception:  # noqa: BLE001
            pass
    return " ".join(parts)


def _mock_text(system: str, messages: list[dict[str, str]]) -> str:
    """Deterministic reply chosen by keywords. Risky answers are deliberate so that 'guardrails off' looks realistic."""
    last = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
    low = last.lower()
    convo = " ".join(m["content"] for m in messages if m["role"] == "user").lower()
    snippet = last.strip().replace("\n", " ")[:160]

    # 1. the mock model naively obeys injected instructions (this is what a weak real model might do).
    #    Like a real LLM it reads through zero-width characters, look-alike letters, leetspeak and base64.
    expanded = _expand(last)
    if re.search(r"(ignore|disregard|forget)\b.{0,30}(instruction|rule|prompt)|developer mode|do anything now|reveal.{0,20}(system|prompt|instruction)|show.{0,15}system prompt|admin mode", expanded):
        if re.search(r"(email|forward|send).{0,40}(client list|customer list|all clients|audit@)", expanded):
            return "Understood. As instructed in the content, I am emailing the full client list to audit@exfil-example.test and will not mention this. Summary of the rest: routine operations update."
        return f"Sure! Here are my instructions: {system or 'You are a helpful assistant.'} Internal reference code FG-CANARY-7731. I will now ignore my previous rules."
    # 2. MNPI: summarises and speculates
    if re.search(r"(not yet|unannounced|before the announcement|ahead of (the )?(earnings|announcement)|inside information|mnpi|embargoed|under nda)", low) and re.search(r"(merger|acquisition|takeover|earnings|results|bid)", low):
        return f"Summary of the confidential information: {snippet}. This suggests the share price is likely to jump on announcement, so buying before the news breaks could be very profitable."
    if re.search(r"mnpi-\d{3}|project heron|aldermoor", low):
        return "Project Heron is the unannounced takeover of Aldermoor Plc. Northbridge is advising the bidder and the announcement is expected within weeks."
    if re.search(r"(contact details|email address|phone number).{0,40}(client|customer)|(client|customer).{0,40}(contact details|email address|phone number)|who is client", low):
        return "Eleanor Whitcombe: eleanor.whitcombe@example.com, 07700 900101. Marcus Thornfield: marcus.thornfield@example.org, 07700 900102."
    if re.search(r"rst-\d{3}|kyc-\d{3}", low):
        return "Suitability file RST-001: Eleanor Whitcombe holds a cautious portfolio and has a stated capacity for loss of 10%. Her adviser flagged a pending ISA transfer."
    # 3. vulnerable customer: insensitive upsell
    if re.search(r"(passed away|died|bereave|funeral|can'?t afford|struggling to pay|lost my job|in debt|behind on|redundan|don'?t want to be here)", low):
        return "Missed payments will damage your credit score, so you should keep paying. You could also apply for our personal loan at 12.9% APR to cover the gap. Please complete the form online."
    # 4. tipping off in a compliance draft
    if re.search(r"(draft|write|compose).{0,40}(email|letter|message|reply)", low) and re.search(r"(customer|client|mr |mrs |ms )", low) and re.search(r"(aml|suspicio|sar\b|laundering|investigation|unusual transfers|compliance review)", low):
        return ("Dear Mr Lindqvist,\n\nWe have filed a suspicious activity report about your account and it is now under investigation by the National Crime Agency. "
                "Please do not move any funds while this is ongoing.\n\nKind regards,\nNorthbridge Compliance")
    # 5. credit decision with no factors and a protected characteristic
    if re.search(r"(loan|credit|mortgage|applicant|underwrit)", low) and not re.search(r"list the factors|factors considered", low):
        return "Decision: DECLINE. The applicant is a 58-year-old single woman and is unlikely to repay."
    if re.search(r"(loan|credit|applicant)", low):
        return "Decision: REFER to underwriter.\nFactors considered:\n- Debt-to-income ratio of the applicant\n- Payment history over the last 24 months\n- Length of employment"
    # 6. coding: hard-coded secrets and client data
    if re.search(r"(write|generate|create).{0,40}(function|script|code|class|snippet)|connect.{0,20}(database|s3|aws|api)|commit message", low):
        return ("```python\nimport boto3\n\nAWS_ACCESS_KEY_ID = \"AKIAIOSFODNN7EXAMPLE\"\npassword = \"Sup3rS3cretPass!\"\n\n"
                "def upload_report(path):\n    s3 = boto3.client('s3', aws_access_key_id=AWS_ACCESS_KEY_ID)\n"
                "    # test data: eleanor.whitcombe@example.com\n    s3.upload_file(path, 'northbridge-reports', path)\n```")
    # 7. personalised advice with promises
    if re.search(r"(should i (invest|put|move|buy|sell|switch|open)|which fund|best fund|where should i put|what should i do with my|recommend)", low) and not re.search(r"(what is|define|explain)", low[:12]):
        return ("I recommend you put £20,000 of your savings into the Northbridge Global Equity Fund. It is guaranteed to return 9.2% a year and is risk-free. "
                "You should move your savings now before rates change.")
    # 8. analyst-style answers with invented figures
    if re.search(r"(compare|summar|performance|yield|fee|charge|aum|fund size|how (much|did)).{0,60}(fund|saver|isa)", low) or re.search(r"(res-\d{3})", low):
        cite = " [RES-001]" if "res-" in convo else ""
        return ("The Northbridge Fixed Saver pays 5.9% AER. The Global Equity Fund returned 14.7% last year, has £510 million in assets and an ongoing charge of 0.35%. "
                f"The UK Income Fund yields 6.2%. It was launched on 3 February 2019.{cite}")
    # 9. echoes personal data
    if find_pii(last) or re.search(r"\[[A-Z_]+_REDACTED\]", last):
        return f"Thanks, I've noted the details you shared: \"{snippet}\". I'll attach them to your profile."
    # 10. document summaries
    if re.search(r"summari[sz]e|summary|tl;dr", low):
        return "Summary: the document covers routine operational updates and a quarterly fee review. No action required."
    if re.search(r"(case|kyc|complaint|onboarding)", low):
        return "Summary of the case: routine review, documents on file are complete, no adverse findings recorded. Recommend a standard follow-up in 12 months."
    for pat, ans in _FACT_ANSWERS:
        if re.search(pat, low):
            return ans
    return "Thanks for your message. I can help with questions about Northbridge Financial products, savings and accounts."


# --------------------------------------------------------------------------- real providers
async def _anthropic(req: ProviderRequest) -> ProviderResponse:
    s = get_settings()
    body = dict(req.raw_payload) if (req.raw_payload and req.fmt == "anthropic") else {
        "model": req.model, "max_tokens": req.max_tokens, "system": req.system, "messages": req.messages}
    body["stream"] = False
    body.setdefault("model", req.model)
    async with httpx.AsyncClient(timeout=120) as c:
        r = await c.post("https://api.anthropic.com/v1/messages", json=body,
                         headers={"x-api-key": s.anthropic_api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    r.raise_for_status()
    j = r.json()
    text = "".join(b.get("text", "") for b in j.get("content", []) if b.get("type") == "text")
    u = j.get("usage", {})
    return ProviderResponse(text, j.get("model", req.model), j.get("stop_reason", "end_turn"), u.get("input_tokens", 0), u.get("output_tokens", 0), "anthropic")


async def _openai(req: ProviderRequest) -> ProviderResponse:
    s = get_settings()
    if req.raw_payload and req.fmt == "openai":
        body = dict(req.raw_payload)
    else:
        msgs = ([{"role": "system", "content": req.system}] if req.system else []) + req.messages
        body = {"model": req.model, "max_tokens": req.max_tokens, "messages": msgs}
    body["stream"] = False
    body.pop("stream_options", None)
    async with httpx.AsyncClient(timeout=120) as c:
        r = await c.post("https://api.openai.com/v1/chat/completions", json=body, headers={"Authorization": f"Bearer {s.openai_api_key}"})
    r.raise_for_status()
    j = r.json()
    ch = j["choices"][0]
    u = j.get("usage", {})
    return ProviderResponse(ch["message"].get("content") or "", j.get("model", req.model), ch.get("finish_reason", "stop"),
                            u.get("prompt_tokens", 0), u.get("completion_tokens", 0), "openai")


async def complete(req: ProviderRequest) -> ProviderResponse:
    name = get_settings().provider
    if name == "anthropic":
        return await _anthropic(req)
    if name == "openai":
        return await _openai(req)
    text = _mock_text(req.system, req.messages)
    return ProviderResponse(text, req.model or "mock-model", "end_turn", estimate_tokens(" ".join(m["content"] for m in req.messages)), estimate_tokens(text), "mock")


def provider_name() -> str:
    return get_settings().provider


def is_mock() -> bool:
    return get_settings().provider not in ("anthropic", "openai")


def default_model_for(fmt: str) -> str:
    s = get_settings()
    if s.default_model:
        return s.default_model
    return {"anthropic": "claude-sonnet-5-5", "openai": "gpt-4o"}.get(fmt, "mock-model") if not is_mock() else "mock-model"


