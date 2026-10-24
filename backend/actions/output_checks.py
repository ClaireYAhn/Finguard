"""Output-stage checks OUT-01 .. OUT-11."""
from __future__ import annotations

import re

from . import dataref
from .base import Ctx, RuleConfig, make_result, register, violation_status
from .figures import approved_facts, approved_set, extract_figures, fmt, is_supported
from .pii import find_pii, find_secrets, redact
from .textutil import has_zero_width, is_definitional, negated_before, normalise, snippet, split_sentences  # noqa: F401


def _out(ctx: Ctx) -> str:
    return ctx.output or ctx.text


def _passed(rule: RuleConfig, name: str, ctype: str, msg: str):
    return make_result(rule, name, ctype, explanation=msg)


# ---------------------------------------------------------------- OUT-01
_PROMISE = [
    (re.compile(r"\bguaranteed\b", re.I), "targeted (not guaranteed)"),
    (re.compile(r"\bguarantees\b", re.I), "aims for (not a guarantee of)"),
    (re.compile(r"\bgua?rantee\b(?! of)", re.I), "no guarantee"),
    (re.compile(r"\brisk[- ]?free\b", re.I), "lower risk (your capital may still be at risk)"),
    (re.compile(r"\b(?:no|zero|without any)\s+risk\b", re.I), "lower risk"),
    (re.compile(r"\b(?:can(?:'|no)t|cannot|won't|will not)\s+(?:possibly\s+)?lose\b", re.I), "could lose value"),
    (re.compile(r"\bwill\s+(?:definitely|certainly|surely|undoubtedly|always)\s+(grow|rise|increase|outperform|beat|earn|double|return|pay)", re.I), r"may \1"),
    (re.compile(r"\b(?:certain|sure|bound)\s+to\s+(grow|rise|increase|outperform|beat|earn|double|pay)", re.I), r"may \1"),
    (re.compile(r"\bsure[- ]thing\b|\bno[- ]brainer\b", re.I), "an option to consider"),
    (re.compile(r"\byou(?:'ll| will)\s+(?:definitely\s+|certainly\s+)?(?:earn|make|get|receive)\s+(?:a\s+)?(?=[£$€\d])", re.I), "you may potentially earn "),
]


def _promissory_hits(text: str) -> list[tuple[re.Pattern, re.Match]]:
    hits = []
    for rx, _ in _PROMISE:
        for m in rx.finditer(text):
            if negated_before(text, m.start(), 18) or re.match(r"(?i)\bnot\s+guaranteed", text[max(0, m.start() - 4):m.end() + 12]):
                continue
            hits.append((rx, m))
    return hits


@register("OUT-01", "Promissory and misleading language", "pattern")
def out01(ctx: Ctx, rule: RuleConfig):
    text = _out(ctx)
    hits = _promissory_hits(text)
    if not hits:
        return _passed(rule, "Promissory and misleading language", "pattern", "No promissory or misleading performance language.")
    ev = [f"...{snippet(text, m.start(), m.end(), 15)}..." for _, m in hits][:6]
    new = text
    if rule.action in ("modify", "escalate"):
        for rx, repl in _PROMISE:
            new = rx.sub(lambda m, repl=repl: m.group() if negated_before(m.string, m.start(), 18) else m.expand(repl), new)
        if _promissory_hits(new):  # could not soften safely -> drop offending sentences
            new = " ".join(s for s in split_sentences(new) if not _promissory_hits(s))
    return make_result(
        rule, "Promissory and misleading language", "pattern", status=violation_status(rule), evidence=ev, new_text=new if rule.action == "modify" else None,
        explanation="Language that promises or guarantees investment outcomes was softened to a fair, balanced statement.",
    )


# ---------------------------------------------------------------- OUT-02
_ADV_TRIG = re.compile(r"\b(you should|you ought to|you need to|you must|you'd be better off|best (?:option|choice) for you|i (?:would |'d )?(?:strongly )?(?:recommend|suggest|advise)\b|my advice\b|go ahead and|the right move for you)", re.I)
_ADV_VERB = re.compile(r"\b(invest|buy|sell|switch|move|put|transfer|allocate|withdraw|remortgage|pay off|open an?|stake|hold|diversify|consolidate|take out|fund|isa|pension|savings|shares?|bonds?|fund)\b", re.I)
_REFERRAL = "I can't give personal recommendations, but I can share general information about our products. For advice that suits your circumstances, please speak to a regulated financial adviser."


def _advice_sentences(text: str) -> list[str]:
    out = []
    for s in split_sentences(text):
        m = _ADV_TRIG.search(s)
        if m and _ADV_VERB.search(s) and not negated_before(s, m.start(), 25):
            out.append(s)
    return out


@register("OUT-02", "Advice boundary", "pattern")
def out02(ctx: Ctx, rule: RuleConfig):
    text = _out(ctx)
    bad = _advice_sentences(text)
    if not bad:
        return _passed(rule, "Advice boundary", "pattern", "No personalised investment recommendation found.")
    new = text
    if rule.action == "modify":
        parts = split_sentences(text)
        res, inserted = [], False
        for s in parts:
            if s in bad:
                if not inserted:
                    res.append(_REFERRAL)
                    inserted = True
            else:
                res.append(s)
        new = " ".join(res)
    return make_result(rule, "Advice boundary", "pattern", status=violation_status(rule), evidence=[b[:140] for b in bad[:4]],
                       new_text=new if rule.action == "modify" else None,
                       explanation="A personalised recommendation was replaced with general information and a referral to a regulated adviser.")


# ---------------------------------------------------------------- OUT-03
_METRIC_KW = [
    ("platform_fee", r"platform fee|platform charge"), ("dealing_fee", r"dealing fee|trading fee"),
    ("ongoing_charge", r"ongoing charge|ocf|annual charge|charges? "), ("return_3y_annualised", r"3[- ]year|three[- ]year|annualised"),
    ("return_1y", r"return|performance|grew|gained|delivered|1[- ]year|one[- ]year|last year"), ("yield", r"yield|income"),
    ("overdraft_rate", r"overdraft"), ("rate", r"\brate\b|aer|interest|pays|earn"), ("fund_size", r"fund size|assets|aum|size"),
    ("annual_allowance", r"allowance"), ("minimum_deposit", r"minimum|min\. deposit"),
]


def _entity_in(sentence: str) -> str | None:
    low = sentence.lower()
    best, blen = None, 0
    for f in approved_facts():
        for name in [f["entity"], *f.get("aliases", [])]:
            if name.lower() in low and len(name) > blen:
                best, blen = f["entity"], len(name)
    return best


def _lookup(entity: str, sentence: str, unit: str) -> dict | None:
    low = sentence.lower()
    cands = [f for f in approved_facts() if f["entity"] == entity and f["unit"] == unit]
    if not cands:
        return None
    for metric, kw in _METRIC_KW:
        if re.search(kw, low):
            for f in cands:
                if f["metric"] == metric:
                    return f
    return cands[0] if len(cands) == 1 else None


@register("OUT-03", "Grounding of figures", "deterministic")
def out03(ctx: Ctx, rule: RuleConfig):
    text = _out(ctx)
    approved = approved_set()
    ctx_figs = set()
    for s in ctx.segments:
        if s.kind != "assistant":
            for f in extract_figures(s.text):
                ctx_figs.add((f.unit, f.value if f.unit == "date" else round(float(f.value), 4)))
    figs = extract_figures(text)
    if not figs:
        return _passed(rule, "Grounding of figures", "deterministic", "No figures to verify.")
    sent_spans, pos = [], 0
    for s in split_sentences(text):
        i = text.find(s, pos)
        sent_spans.append((i, i + len(s), s))
        pos = i + len(s)
    edits: list[tuple[int, int, str]] = []
    ev: list[str] = []
    for f in figs:
        sent = next((s for a, b, s in sent_spans if a <= f.start < b), text)
        ent = _entity_in(sent)
        key = (f.unit, f.value if f.unit == "date" else round(float(f.value), 4))
        if ent and f.unit in ("pct", "gbp"):
            # entity-aware: the figure must belong to the entity named in the same sentence
            ent_vals = {("pct" if x["unit"] == "pct" else x["unit"], round(float(x["value"]), 4)) for x in approved_facts() if x["entity"] == ent}
            if key in ent_vals or key in ctx_figs or (f.unit == "pct" and f.value in (0, 100)):
                continue
        elif is_supported(f, approved, ctx_figs):
            continue
        fact = _lookup(ent, sent, f.unit) if ent and f.unit != "date" else None
        if fact:
            right = fmt(f.unit, float(fact["value"]))
            ev.append(f"{f.text.strip()} stated vs {right} approved ({fact['entity']}, {fact['metric'].replace('_', ' ')})")
            edits.append((f.start, f.end, right))
        else:
            ev.append(f"{f.text.strip()} has no approved source")
            edits.append((f.start, f.end, "[figure removed: not in approved data]"))
    if not ev:
        return _passed(rule, "Grounding of figures", "deterministic", f"All {len(figs)} figure(s) match approved data or the user's own input.")
    new = text
    if rule.action == "modify":
        for a, b, r in sorted(edits, reverse=True):
            new = new[:a] + r + new[b:]
    return make_result(rule, "Grounding of figures", "deterministic", status=violation_status(rule), evidence=ev[:10],
                       new_text=new if rule.action == "modify" else None,
                       explanation=f"{len(ev)} of {len(figs)} figure(s) were not supported by approved data; each was corrected or removed.")


# ---------------------------------------------------------------- OUT-04
_CITE = re.compile(r"\[(RES-\d{3}|RST-\d{3}|CASE-\d{3}|KYC-\d{3}|MNPI-\d{3})\]")


@register("OUT-04", "Source citation requirement", "deterministic")
def out04(ctx: Ctx, rule: RuleConfig):
    text = _out(ctx)
    facts = extract_figures(text)
    min_figs = int(rule.thresholds.get("min_figures", 1))
    cited = _CITE.findall(text)
    unknown = [c for c in cited if c not in dataref.documents()]
    if len(facts) < min_figs and not re.search(r"\b(according to|analysts? (?:say|expect)|research shows)\b", text, re.I):
        return _passed(rule, "Source citation requirement", "deterministic", "No factual claims requiring a citation.")
    if cited and not unknown:
        return _passed(rule, "Source citation requirement", "deterministic", f"Cites approved sources: {', '.join(sorted(set(cited)))}.")
    new = text
    ev = []
    if unknown:
        ev.append(f"citation(s) to unknown documents: {', '.join(unknown)}")
        for u in unknown:
            new = new.replace(f"[{u}]", "[unverified source removed]")
    if not cited:
        ev.append("factual claims with no source citation")
    note = "\n\nSources: none verified. Treat the claims above as unsourced until checked against approved research (e.g. [RES-001])."
    new = new + note if rule.action == "modify" else text
    return make_result(rule, "Source citation requirement", "deterministic", status=violation_status(rule), evidence=ev,
                       new_text=new if rule.action == "modify" else None,
                       explanation="Research output must cite approved documents; an unsourced-claims notice was added.")


# ---------------------------------------------------------------- OUT-05
@register("OUT-05", "Required disclosures", "deterministic")
def out05(ctx: Ctx, rule: RuleConfig):
    text = _out(ctx)
    discl = ctx.settings.get("disclosures", [])
    norm = normalise(text)
    missing = []
    for d in discl:
        body, when = (d, None) if isinstance(d, str) else (d["text"], d.get("when_regex"))
        if when and not re.search(when, text, re.I):
            continue
        if normalise(body) not in norm:
            missing.append(body)
    if not missing:
        return _passed(rule, "Required disclosures", "deterministic", "Required disclosures already present." if discl else "No disclosures configured.")
    new = text.rstrip() + "\n\n" + "\n".join(missing)
    return make_result(rule, "Required disclosures", "deterministic", status=violation_status(rule), evidence=[m[:80] for m in missing],
                       new_text=new if rule.action == "modify" else None,
                       explanation="Required regulatory disclosure(s) were appended (only once; checks for existing text first).")


# ---------------------------------------------------------------- OUT-06
_VULN = [
    ("bereavement", r"\b(passed away|died|death of my|bereave\w*|funeral|lost my (?:husband|wife|partner|mum|mother|dad|father|son|daughter))\b"),
    ("financial difficulty", r"\b(can'?t|cannot|unable to|struggling to|struggle to) (?:afford|pay|cope|make ends meet|keep up)\b|\b(?:behind on|missed) (?:my |our )?(?:payments?|rent|mortgage)\b|\bin debt\b|\blost my job\b|\bmade redundant\b|\bbailiff\w*\b|\bfood ?bank\b"),
    ("health or capacity", r"\b(dementia|memory (?:problems|loss)|i(?:'m| am) (?:very )?confused|i don'?t understand (?:any of )?(?:this|these)|mental health|depress\w*|anxiety|panic attacks?)\b"),
    ("distress", r"\b(scared|terrified|desperate|hopeless|overwhelmed|can'?t cope|at my wit'?s end)\b"),
    ("self-harm risk", r"\b(suicid\w*|kill myself|end it all|self[- ]?harm|don'?t want to be here|no reason to live)\b"),
]
_FIRST = re.compile(r"\b(i|i'm|i am|i've|i'd|my|me)\b", re.I)
SUPPORT = ("I'm really sorry to hear that, and thank you for telling us. You don't need to deal with this alone. "
           "I'm passing your message to a member of our specialist support team, who will contact you personally and can talk through options such as payment breaks or adjusted arrangements. "
           "There's no pressure to make any decisions today.")
SUPPORT_CRISIS = (" If you are in immediate distress, please contact the Samaritans free on 116 123 (UK), or emergency services on 999.")


@register("OUT-06", "Vulnerability and distress detection", "pattern")
def out06(ctx: Ctx, rule: RuleConfig):
    hits: list[tuple[str, str]] = []
    crisis = False
    third = bool(rule.thresholds.get("third_person", False))
    for seg in ctx.segments:
        if seg.kind != "user":
            continue
        for s in split_sentences(seg.text):
            low = normalise(s)
            if is_definitional(s):
                continue
            for name, pat in _VULN:
                m = re.search(pat, low)
                if m and (third or _FIRST.search(low)) and not negated_before(low, m.start(), 25):
                    hits.append((name, snippet(low, m.start(), m.end(), 12)))
                    crisis = crisis or name == "self-harm risk"
    if not hits:
        return _passed(rule, "Vulnerability and distress detection", "pattern", "No signs of vulnerability or distress.")
    kinds = sorted({h[0] for h in hits})
    return make_result(rule, "Vulnerability and distress detection", "pattern", status=violation_status(rule), open_case=True,
                       evidence=[f"{k}: ...{s}..." for k, s in hits[:4]],
                       explanation=f"Signs of customer vulnerability ({', '.join(kinds)}). The reply was replaced with a supportive message and a human colleague was alerted (Consumer Duty).",
                       safe_message=SUPPORT + (SUPPORT_CRISIS if crisis else ""))


# ---------------------------------------------------------------- OUT-07
@register("OUT-07", "Confidentiality and PII leakage", "pattern")
def out07(ctx: Ctx, rule: RuleConfig):
    text = _out(ctx)
    allow = set(rule.thresholds.get("allow_types", []))
    ev: list[str] = []
    new = text
    finds = [f for f in find_pii(text) if f.kind not in allow]
    if finds:
        new = redact(text, finds)
        ev += [f.masked for f in finds][:10]
    sysleak = False
    sys_text = " ".join(s.text for s in ctx.segments if s.kind == "system")
    words = re.findall(r"\w+", normalise(sys_text))
    nout = " ".join(re.findall(r"\w+", normalise(text)))
    for i in range(0, max(0, len(words) - 7)):
        if " ".join(words[i:i + 8]) in nout:
            sysleak = True
            break
    for marker in ctx.settings.get("system_prompt_markers", []) + ["fg-canary-7731"]:
        if marker.lower() in text.lower():
            sysleak = True
    if re.search(r"\b(my|the) (system prompt|hidden instructions|initial instructions) (is|are|says?|reads?)\b", text, re.I):
        sysleak = True
    if sysleak:
        ev.append("output reproduces system prompt / internal instructions")
    for did, doc in dataref.documents().items():
        if doc["classification"] in ("restricted", "mnpi") and (did in text or doc["title"].lower() in text.lower()) and not dataref.can_access(ctx.role, doc):
            ev.append(f"restricted document {did} content referenced")
            sysleak = True
    if not ev:
        return _passed(rule, "Confidentiality and PII leakage", "pattern", "No personal data, secrets or internal instructions in the output.")
    if sysleak:
        return make_result(rule, "Confidentiality and PII leakage", "pattern", status="blocked" if rule.action in ("block", "escalate") else violation_status(rule),
                           severity=rule.severity, evidence=ev, safe_message="I can't share internal instructions or restricted information.",
                           explanation="The output exposed internal instructions or restricted material and was withheld.",
                           new_text=None)
    return make_result(rule, "Confidentiality and PII leakage", "pattern", status=violation_status(rule), evidence=ev,
                       new_text=new if rule.action == "modify" else None,
                       explanation="Personal or financial identifiers in the model output were redacted before release.")


# ---------------------------------------------------------------- OUT-08
_PROT = re.compile(r"\b(aged? \d{2}|\d{2}[- ]year[- ]old|elderly|older (?:applicant|customer|person)|young(?:er)? (?:applicant|customer|person)|woman|women|female|male|gender|race|racial|ethnic\w*|religio\w*|muslim|jewish|christian|hindu|marital status|single (?:mother|woman|man|parent)|pregnan\w*|disabilit\w*|disabled|sexual orientation|nationality|immigrant|foreign(?:er)?)\b", re.I)
_DECISION = re.compile(r"\b(declin\w*|reject\w*|den(?:y|ied|ial)|refus\w*|unlikely to repay|high(?:er)?[- ]risk|risky|not creditworthy|less likely|poor (?:candidate|risk)|approve\w*|lower limit|higher rate|unsuitable)\b", re.I)


@register("OUT-08", "Fairness screen", "pattern")
def out08(ctx: Ctx, rule: RuleConfig):
    text = _out(ctx)
    ev = []
    for s in split_sentences(text):
        for m in _PROT.finditer(s):
            if _DECISION.search(s) and not negated_before(s, m.start(), 45) and not re.search(r"(?i)(not|never|no) (?:been )?(?:used|considered|taken into account)", s):
                ev.append(f"'{m.group().strip()}' in decision reasoning: {s[:110]}")
                break
    if not ev:
        return _passed(rule, "Fairness screen", "pattern", "No protected characteristics used in decision reasoning.")
    return make_result(rule, "Fairness screen", "pattern", status=violation_status(rule), evidence=ev[:4], open_case=rule.action == "escalate",
                       explanation="Reasoning appears to rely on a protected characteristic; the decision was withheld for human review.",
                       safe_message="This recommendation was withheld because its reasoning referred to a protected characteristic. It has been sent for human review.")


# ---------------------------------------------------------------- OUT-09
_TIP = re.compile(r"\b(suspicious (?:activity|transaction) report|\bsars?\b|\bstrs?\b|reported (?:you|your account|this) to (?:the )?(?:nca|police|authorities|fiu|national crime agency)|money laundering (?:investigation|suspicion|concern|report)|(?:under|subject to) (?:a |an )?(?:criminal |police |aml )?investigation|we (?:suspect|believe) (?:you|your)|law enforcement|financial intelligence unit|national crime agency|filed a report (?:about|on) (?:you|your))\b", re.I)
NEUTRAL = ("Draft withheld and referred to the MLRO: it may disclose a suspicion or report about the customer (tipping-off risk). "
           "If a customer message is needed, use neutral wording, e.g. \"We are carrying out a routine review of your account and need some information from you.\"")


@register("OUT-09", "AML tipping-off protection", "pattern")
def out09(ctx: Ctx, rule: RuleConfig):
    text = _out(ctx)
    customer_facing = bool(re.search(r"(?im)^\s*(dear|hello|hi)\b", text)) or bool(re.search(
        r"\b(draft|email|letter|message|reply)\b.{0,30}\b(to|for)\b.{0,20}\b(customer|client|account holder|him|her|them|mr|mrs|ms)\b", normalise(ctx.user_input), re.I)) or bool(ctx.settings.get("always_customer_facing"))
    ms = [m for m in _TIP.finditer(text) if not negated_before(text, m.start(), 20)]
    if not ms or not customer_facing:
        return _passed(rule, "AML tipping-off protection", "pattern", "No tipping-off language in a customer-facing draft." if not ms else "AML terms present but the text is not a customer-facing draft.")
    return make_result(rule, "AML tipping-off protection", "pattern", status=violation_status(rule), open_case=rule.action == "escalate",
                       evidence=[f"...{snippet(text, m.start(), m.end(), 20)}..." for m in ms[:4]], safe_message=NEUTRAL,
                       explanation="A customer-facing draft disclosed AML/SAR suspicion, which risks tipping-off under POCA 2002 / MLR 2017.")


# ---------------------------------------------------------------- OUT-10
_DEC_WORDS = re.compile(r"\b(approve\w*|declin\w*|reject\w*|refer(?:red)?|recommend\w* (?:approval|decline|rejection)|decision|outcome|credit score|affordab\w+)\b", re.I)
_LISTITEM = re.compile(r"(?m)^\s*(?:[-*•]|\d+[.)])\s+\S+")


@register("OUT-10", "Explainability of decisions", "deterministic")
def out10(ctx: Ctx, rule: RuleConfig):
    text = _out(ctx)
    if not _DEC_WORDS.search(text):
        return _passed(rule, "Explainability of decisions", "deterministic", "Output is not a decision recommendation.")
    need = int(rule.thresholds.get("min_factors", 2))
    items = len(_LISTITEM.findall(text))
    inline = re.search(r"(?i)(?:based on|factors? (?:considered|used)|because of|reasons?)\s*:?\s*([^.\n]+)", text)
    inline_n = len(re.split(r",|;| and ", inline.group(1))) if inline else 0
    has_label = bool(re.search(r"(?i)factors?|reasons?|criteria|based on|because", text))
    n = max(items, inline_n)
    if has_label and n >= need:
        return _passed(rule, "Explainability of decisions", "deterministic", f"Decision lists {n} supporting factors.")
    return make_result(rule, "Explainability of decisions", "deterministic", status=violation_status(rule), open_case=rule.action == "escalate",
                       evidence=[f"{n} factor(s) stated, {need} required"],
                       explanation="A decision-support output must state the factors it relied on; this one did not, so it was sent for human review.",
                       safe_message="This decision recommendation did not state the factors it was based on, so it has been withheld and sent for human review.")


# ---------------------------------------------------------------- OUT-11
@register("OUT-11", "Code safety", "pattern")
def out11(ctx: Ctx, rule: RuleConfig):
    text = _out(ctx)
    secrets = find_secrets(text)
    ev = [f.masked for f in secrets]
    new = text
    block = any("PRIVATE KEY" in f.value for f in secrets)
    for f in sorted(secrets, key=lambda x: x.start, reverse=True):
        new = new[:f.start] + "<REDACTED_SECRET: load from environment or a secret manager>" + new[f.end:]
    client_hits = []
    for c in dataref.clients():
        for key in ("name", "email", "phone"):
            if c[key].lower() in text.lower():
                client_hits.append(f"client {key} ({c['id']}) present in generated code/text")
    pii = [f for f in find_pii(text, {"CARD", "IBAN", "NI_NUMBER", "SSN"})]
    ev += [f.masked for f in pii] + client_hits
    if not ev:
        return _passed(rule, "Code safety", "pattern", "No hard-coded secrets or client data found in the generated text.")
    if client_hits or pii:
        new = redact(new, [f for f in find_pii(new, {"CARD", "IBAN", "NI_NUMBER", "SSN"})])
        for c in dataref.clients():
            for key in ("name", "email", "phone"):
                new = re.sub(re.escape(c[key]), "<CLIENT_DATA_REMOVED>", new, flags=re.I)
    status = "blocked" if block and rule.action != "log" else violation_status(rule)
    return make_result(rule, "Code safety", "pattern", status=status, evidence=ev[:8], new_text=new if status == "modified" else None,
                       safe_message="The generated code contained a private key and was withheld." if status == "blocked" else None,
                       explanation="Hard-coded secrets or client data were found in generated code; they were replaced with placeholders.")
