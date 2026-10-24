"""Input-stage checks IN-01 .. IN-05."""
from __future__ import annotations

import base64
import re

from . import dataref
from .base import Ctx, RuleConfig, make_result, register, violation_status
from .pii import find_pii, presidio_extra, redact
from .textutil import has_zero_width, is_definitional, negated_before, normalise, snippet

DOC_ID_RE = re.compile(r"\b(?:RES|RST|MNPI|CASE|KYC)-\d{3}\b")


# ---------------------------------------------------------------- IN-01
@register("IN-01", "Sensitive data redaction", "pattern")
def in01(ctx: Ctx, rule: RuleConfig):
    types = rule.thresholds.get("types")
    tset = set(types) if types else None
    evidence: list[str] = []
    counts: dict[str, int] = {}
    use_presidio = bool(ctx.settings.get("use_presidio"))
    for seg in ctx.segments:
        if seg.kind == "assistant" or seg.kind == "system":
            continue
        found = find_pii(seg.text, tset)
        if use_presidio:
            found = sorted(found + presidio_extra(seg.text), key=lambda f: f.start)
        if not found:
            continue
        ctx.seg_updates[seg.index] = redact(seg.text, found)
        for f in found:
            evidence.append(f.masked)
            counts[f.kind] = counts.get(f.kind, 0) + 1
    if not evidence:
        return make_result(rule, "Sensitive data redaction", "pattern", explanation="No sensitive personal or financial identifiers found.")
    summary = ", ".join(f"{n} {k}" for k, n in sorted(counts.items()))
    last = ctx.segments[-1].index if ctx.segments else 0
    return make_result(
        rule, "Sensitive data redaction", "pattern", status=violation_status(rule) if rule.action != "log" else "pass",
        explanation=f"Found {summary}. Values were redacted before reaching the model and masked in evidence.",
        evidence=evidence[:20], new_text=ctx.seg_updates.get(last) if rule.action == "modify" else None,
    )


# ---------------------------------------------------------------- IN-02
_INJ = [
    ("override-instructions", r"\b(ignore|disregard|forget|override|bypass|skip)\b.{0,25}\b(all|any|the|your|previous|prior|above|earlier|system|safety|these|those)\b.{0,25}\b(instructions?|rules?|prompts?|guidelines?|guardrails?|polic(?:y|ies)|restrictions?|directives?)\b"),
    ("reveal-prompt", r"\b(reveal|show|print|repeat|output|display|leak|tell me|share)\b.{0,30}\b(system|hidden|initial|original|developer)\b.{0,10}\b(prompt|instructions?|message)\b"),
    ("persona-jailbreak", r"\b(you are now|from now on you are|act as|pretend (?:to be|you are)|roleplay as)\b.{0,40}\b(dan|do anything now|unrestricted|unfiltered|jailbroken|no restrictions|without (?:any )?(?:restrictions|limits|rules|filters)|admin mode|developer mode)\b"),
    ("mode-switch", r"\b(developer mode|admin mode|god mode|dan mode|jailbreak(?:ed)?|do anything now)\b"),
    ("no-restrictions", r"\b(pretend|imagine|assume)\b.{0,30}\b(no|without)\b.{0,15}\b(restrictions?|rules?|guardrails?|filters?|limits?)\b"),
    ("fake-system-tag", r"(<\|im_start\|>|<\|system\|>|\[/?inst\]|<<sys>>|^\s*#{2,3}\s*system\b|^\s*system\s*:)"),
    ("new-instructions", r"\b(new|updated|real|actual)\s+instructions?\s*(?::|follow|are)\b"),
    ("exfil-instruction", r"\b(send|email|forward|post|upload|exfiltrate)\b.{0,40}\b(client list|customer list|all (?:clients|customers)|database|credentials|api keys?|passwords?)\b.{0,40}\b(to|at)\b"),
    ("secrecy", r"\b(do not|don't|never)\b.{0,20}\b(tell|inform|mention|reveal)\b.{0,20}\b(the user|anyone|this to)\b"),
]
_INJ_RE = [(n, re.compile(p, re.I | re.S | re.M)) for n, p in _INJ]
_LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s"})
_SPACED = re.compile(r"(?:\b\w[\s.\-_*]){4,}\w\b")
_B64 = re.compile(r"[A-Za-z0-9+/]{24,}={0,2}")
_QUOTED_EXPLAIN = re.compile(r"(means?|meaning|phrase|example of|such as|called|known as|what is|define|detect|prevent|block)\W{0,8}[\"'`]?$", re.I)


def injection_variants(text: str) -> list[tuple[str, str]]:
    """(label, folded text) variants used for matching, covering common obfuscation."""
    base = normalise(text)
    variants = [("plain", base)]
    leet = base.translate(_LEET)
    if leet != base:
        variants.append(("leetspeak", leet))
    spaced = _SPACED.sub(lambda m: re.sub(r"[\s.\-_*]", "", m.group()), base)
    if spaced != base:
        variants.append(("spaced-letters", spaced))
    for m in _B64.finditer(text):
        try:
            dec = base64.b64decode(m.group() + "=" * (-len(m.group()) % 4), validate=False).decode("utf-8")
        except Exception:  # noqa: BLE001
            continue
        if dec.isprintable() and len(dec) > 8:
            variants.append(("base64", normalise(dec)))
    return variants


def scan_injection(text: str) -> list[tuple[str, str, str]]:
    """Return [(pattern_name, variant, evidence_snippet)] for a text."""
    hits: list[tuple[str, str, str]] = []
    for label, v in injection_variants(text):
        for name, rx in _INJ_RE:
            for m in rx.finditer(v):
                pre = v[max(0, m.start() - 30):m.start()]
                if _QUOTED_EXPLAIN.search(pre.rstrip()) or negated_before(v, m.start(), 20):
                    continue
                hits.append((name, label, snippet(v, m.start(), m.end(), 10)))
                break
        if hits:
            break
    return hits


@register("IN-02", "Prompt injection and jailbreak", "pattern")
def in02(ctx: Ctx, rule: RuleConfig):
    ev: list[str] = []
    indirect = False
    zw = False
    for seg in ctx.segments:
        if seg.kind in ("assistant", "system"):
            continue
        if has_zero_width(seg.text):
            zw = True
        for name, variant, snip in scan_injection(seg.text):
            via = "indirect:" + seg.kind if seg.kind in ("tool_result", "document") or "<!--" in seg.text else "direct"
            indirect = indirect or via.startswith("indirect")
            ev.append(f"{via} {name} ({variant}): ...{snip}...")
    # optional model judge (only when enabled, never in mock mode)
    judged = False
    if not ev and rule.thresholds.get("use_model_judge") and ctx.judge and not ctx.provider_is_mock:
        judged = True
        try:
            verdict = ctx.judge("injection", ctx.context_text[-6000:])
        except Exception as exc:  # noqa: BLE001
            if rule.severity == "high":
                return make_result(rule, "Prompt injection and jailbreak", "model", status="blocked", error=str(exc),
                                   explanation="Model judge failed; failing closed (severity high).", evidence=["judge error"],
                                   safe_message="I can't process this request right now.")
            verdict = {"flag": False}
        if verdict.get("flag"):
            ev.append(f"model-judge: {verdict.get('reason', 'flagged')}")
    ctype = "model" if judged else "pattern"
    if not ev:
        note = " Zero-width characters were present and were ignored for matching." if zw else ""
        return make_result(rule, "Prompt injection and jailbreak", ctype, explanation="No injection or jailbreak patterns found." + note,
                           evidence=["zero-width characters present"] if zw else [])
    kind = "Indirect prompt injection (hidden instructions in supplied content)" if indirect else "Direct prompt injection or jailbreak attempt"
    return make_result(
        rule, "Prompt injection and jailbreak", ctype, status=violation_status(rule),
        explanation=f"{kind} detected; the request was stopped before reaching the model.",
        evidence=ev[:6],
        safe_message="I can't follow instructions that try to change my rules or access restricted information. How else can I help?",
    )


# ---------------------------------------------------------------- IN-03
TOPICS = {
    "offtopic": [r"\b(write|compose)\b.{0,20}\b(poem|song|story|essay|joke)\b", r"\brecipe\b", r"\bfootball\b|\bworld cup\b", r"\bweather\b.{0,10}\b(tomorrow|today|forecast)\b", r"\bhoroscope\b", r"\bhomework\b"],
    "political": [r"\bwho should i vote for\b", r"\bwhich party\b.{0,20}\b(vote|support)\b", r"\belection\b.{0,20}\b(opinion|prediction|who will win)\b"],
    "illicit": [r"\bhow (?:do|can|to)\b.{0,25}\b(launder|evade tax|hide (?:money|assets) from|avoid detection|structure deposits)\b", r"\b(launder|smurf)\w*\b.{0,20}\b(money|funds|cash)\b.{0,20}\b(without|undetected|avoid)\b", r"\bevade\b.{0,15}\b(sanctions|kyc|aml)\b"],
    "medical_legal": [r"\b(diagnose|diagnosis)\b", r"\bshould i sue\b", r"\bwrite (?:me )?a (?:will|contract)\b"],
}


@register("IN-03", "Topic and intent control", "pattern")
def in03(ctx: Ctx, rule: RuleConfig):
    wanted = ctx.settings.get("blocked_topics", ["offtopic", "illicit"])
    text = normalise(ctx.user_input or ctx.text)
    hits: list[str] = []
    for topic in wanted:
        for pat in TOPICS.get(topic, []):
            m = re.search(pat, text)
            if m:
                hits.append(f"{topic}: ...{snippet(text, m.start(), m.end(), 10)}...")
                break
    if not hits:
        return make_result(rule, "Topic and intent control", "pattern", explanation="Request is within the allowed scope.")
    msg = ctx.settings.get("redirect_message") or "I'm not able to help with that here, but I'm happy to help with questions about our products and services."
    return make_result(rule, "Topic and intent control", "pattern", status=violation_status(rule), evidence=hits,
                       explanation="Request is outside this assistant's permitted scope; a polite redirect was returned.", safe_message=msg)


# ---------------------------------------------------------------- IN-04
_NONPUBLIC = r"(not yet (?:been )?(?:announced|public|disclosed|released)|unannounced|non-?public|before (?:the |its |their )?(?:announcement|release|results|earnings)|ahead of (?:the )?(?:announcement|earnings|results)|embargoed|under (?:an )?nda|strictly confidential|inside information|insider information|price[- ]sensitive|material non-?public|\bmnpi\b|have not been made public|hasn't been announced|has not been announced|haven't been announced)"
_EVENT = r"(merger|acquisition|takeover|tender offer|buy-?out|earnings|results|profit warning|guidance|dividend (?:cut|increase)|restructuring|bankruptcy|insolvency|delisting|fda approval|trial results|capital raise|rights issue|ceo (?:resign|depart|step)|investigation|settlement|bid for)"
_ASSERT = r"(this is|we have|i have|i've got|here is|here's|received|got hold of|leaked|sitting on|i know|i heard)\b.{0,40}\b(mnpi|inside information|insider information|material non-?public)"


@register("IN-04", "MNPI screening", "pattern")
def in04(ctx: Ctx, rule: RuleConfig):
    text = normalise(ctx.text)
    ev: list[str] = []
    for did in DOC_ID_RE.findall(ctx.text.upper()):
        d = dataref.documents().get(did)
        if d and d["classification"] == "mnpi":
            ev.append(f"reference to MNPI document {did}")
    for d in dataref.documents().values():
        if d["classification"] == "mnpi":
            codename = d["title"].split(":")[0].strip().lower()
            if codename and codename in text and not any(codename in e for e in ev):
                ev.append(f"reference to MNPI codename '{codename}'")
    if not ev and is_definitional(ctx.text) and not re.search(_EVENT, text):
        return make_result(rule, "MNPI screening", "pattern", explanation="Definitional question about MNPI; no non-public information supplied.")
    nonpub = re.search(_NONPUBLIC, text)
    event = re.search(_EVENT, text)
    asserted = re.search(_ASSERT, text)
    if nonpub and event and not negated_before(text, nonpub.start(), 25):
        ev.append(f"non-public marker + corporate event: ...{snippet(text, nonpub.start(), nonpub.end(), 20)}...")
    elif asserted and not negated_before(text, asserted.start(), 15):
        ev.append("user asserts they hold inside information")
    # tickers / names add context but are not required
    if not ev:
        return make_result(rule, "MNPI screening", "pattern", explanation="No indicators of material non-public information.")
    return make_result(
        rule, "MNPI screening", "pattern", status=violation_status(rule), evidence=ev[:5], open_case=rule.action == "escalate",
        explanation="Suspected material non-public information was kept away from the external model and referred to compliance.",
        safe_message="This looks like it may contain inside information, so I haven't processed it. I've passed it to Compliance for review. Please don't share or trade on it.",
    )


# ---------------------------------------------------------------- IN-05
_BULK = re.compile(r"\b(list|show|give me|export|dump|download|send me)\b.{0,25}\b(all|every|entire|full|whole)\b.{0,20}\b(clients?|customers?|accounts?|client list|customer database|database)\b", re.I)


@register("IN-05", "Role-based access control", "deterministic")
def in05(ctx: Ctx, rule: RuleConfig):
    ev: list[str] = []
    allowed = ctx.app.get("allowed_roles") or []
    if allowed and ctx.role not in allowed:
        ev.append(f"role '{ctx.role}' is not permitted to use this application")
    for did in sorted(set(DOC_ID_RE.findall((ctx.user_input or ctx.text).upper()))):
        doc = dataref.documents().get(did)
        if doc and not dataref.can_access(ctx.role, doc):
            ev.append(f"role '{ctx.role}' may not access {did} ({doc['classification']})")
    bulk_roles = set(rule.thresholds.get("bulk_roles", ["operations", "compliance", "admin"]))
    if _BULK.search(ctx.user_input or ctx.text) and ctx.role not in bulk_roles:
        ev.append(f"bulk client-data request by role '{ctx.role}'")
    if not ev:
        return make_result(rule, "Role-based access control", "deterministic", explanation="Role is permitted for the requested data.")
    return make_result(rule, "Role-based access control", "deterministic", status=violation_status(rule), evidence=ev,
                       explanation="The user's role does not permit this access.",
                       safe_message="Your role doesn't have access to that information. If you need it, please contact your manager or Compliance.")
