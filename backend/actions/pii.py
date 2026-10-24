"""Sensitive-data detectors used by IN-01, OUT-07 and the tool guard."""
from __future__ import annotations

import re
from dataclasses import dataclass

from .textutil import mask


@dataclass
class Finding:
    kind: str
    start: int
    end: int
    value: str

    @property
    def masked(self) -> str:
        return mask(self.value, self.kind)


def luhn_ok(digits: str) -> bool:
    d = [int(c) for c in digits if c.isdigit()]
    if not 13 <= len(d) <= 19:
        return False
    total = 0
    for i, n in enumerate(reversed(d)):
        if i % 2:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def iban_ok(iban: str) -> bool:
    s = re.sub(r"\s+", "", iban).upper()
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{11,30}", s) or len(s) > 34:
        return False
    rearr = s[4:] + s[:4]
    num = "".join(str(int(c, 36)) for c in rearr)
    return int(num) % 97 == 1


CARD_RE = re.compile(r"(?<![\d-])(?:\d[ -]?){12,18}\d(?![\d-])")
IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{2,4}){3,8}\b")
SORT_RE = re.compile(r"\b\d{2}-\d{2}-\d{2}\b")
SORT_CTX = re.compile(r"sort\s*code[^0-9]{0,12}(\d{2}[ -]?\d{2}[ -]?\d{2})\b", re.I)
ACCNO_CTX = re.compile(r"(?:account\s*(?:number|no\.?|num)|acc(?:ount)?\s*(?:no\.?|#)|a/c)[^0-9]{0,12}(\d{8})\b", re.I)
NI_RE = re.compile(r"\b(?!BG|GB|NK|KN|TN|NT|ZZ)[A-CEGHJ-PR-TW-Z][A-CEGHJ-NPR-TW-Z]\s?\d{2}\s?\d{2}\s?\d{2}\s?[A-D]\b", re.I)
SSN_RE = re.compile(r"\b(?!000|666|9\d\d)\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b")
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_RE = re.compile(r"(?<![\w.])(?:\+44\s?\(?0?\)?\s?|\(?0)7\d{3}\)?[ -]?\d{3}[ -]?\d{3}\b|(?<![\w.])\+1[ -]?\(?\d{3}\)?[ -]?\d{3}[ -]?\d{4}\b|(?<![\w.])\(?0\d{3,4}\)?[ -]?\d{3}[ -]?\d{3,4}\b")
DOB_RE = re.compile(
    r"(?:\b(?:dob|d\.o\.b\.?|date of birth|born(?: on)?)\b[^0-9A-Za-z]{0,6})"
    r"(\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4}|\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]{3,9}\.?,?\s+\d{4}|[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4}|\d{4}-\d{2}-\d{2})",
    re.I,
)

TOKENS = {
    "CARD": "[CARD_REDACTED]", "IBAN": "[IBAN_REDACTED]", "SORT_CODE": "[SORT_CODE_REDACTED]",
    "ACCOUNT_NO": "[ACCOUNT_NO_REDACTED]", "NI_NUMBER": "[NI_NUMBER_REDACTED]", "SSN": "[SSN_REDACTED]",
    "EMAIL": "[EMAIL_REDACTED]", "SECRET": "[SECRET_REDACTED]", "PHONE": "[PHONE_REDACTED]", "DOB": "[DOB_REDACTED]",
}


SECRET_PATTERNS = [
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
    re.compile(r"\bxox[abp]-[A-Za-z0-9-]{10,}\b"),
    re.compile(r"\b[a-z][a-z0-9+.-]*://[^\s:/@]+:([^\s@/]{3,})@[^\s/]+"),
    re.compile(r"(?i)\b(?:password|passwd|pwd|secret|api[_-]?key|apikey|access[_-]?token|auth[_-]?token|client[_-]?secret)\b\s*[:=]\s*[\"']([^\"'\s]{6,})[\"']"),
]


def find_secrets(text: str) -> list[Finding]:
    out: list[Finding] = []
    for rx in SECRET_PATTERNS:
        for m in rx.finditer(text):
            if m.lastindex:
                val = m.group(m.lastindex)
                if val.lower().startswith(("<redacted", "your_", "changeme", "xxxx", "${", "os.environ", "process.env")):
                    continue
                out.append(Finding("SECRET", m.start(m.lastindex), m.end(m.lastindex), val))
            else:
                out.append(Finding("SECRET", m.start(), m.end(), m.group()))
    return out


def find_pii(text: str, types: set[str] | None = None) -> list[Finding]:
    out: list[Finding] = []

    def want(k: str) -> bool:
        return types is None or k in types

    if want("CARD"):
        for m in CARD_RE.finditer(text):
            digits = re.sub(r"\D", "", m.group())
            if luhn_ok(digits) and len(set(digits)) > 1:
                out.append(Finding("CARD", m.start(), m.end(), m.group()))
    if want("IBAN"):
        for m in IBAN_RE.finditer(text):
            if iban_ok(m.group()):
                out.append(Finding("IBAN", m.start(), m.end(), m.group()))
    if want("SORT_CODE"):
        for m in SORT_RE.finditer(text):
            out.append(Finding("SORT_CODE", m.start(), m.end(), m.group()))
        for m in SORT_CTX.finditer(text):
            if not any(f.start <= m.start(1) < f.end for f in out):
                out.append(Finding("SORT_CODE", m.start(1), m.end(1), m.group(1)))
    if want("ACCOUNT_NO"):
        for m in ACCNO_CTX.finditer(text):
            out.append(Finding("ACCOUNT_NO", m.start(1), m.end(1), m.group(1)))
    if want("NI_NUMBER"):
        for m in NI_RE.finditer(text):
            out.append(Finding("NI_NUMBER", m.start(), m.end(), m.group()))
    if want("SSN"):
        for m in SSN_RE.finditer(text):
            out.append(Finding("SSN", m.start(), m.end(), m.group()))
    if want("EMAIL"):
        for m in EMAIL_RE.finditer(text):
            out.append(Finding("EMAIL", m.start(), m.end(), m.group()))
    if want("PHONE"):
        for m in PHONE_RE.finditer(text):
            digits = re.sub(r"\D", "", m.group())
            if 10 <= len(digits) <= 13 and not any(f.start <= m.start() < f.end for f in out):
                out.append(Finding("PHONE", m.start(), m.end(), m.group()))
    if want("DOB"):
        for m in DOB_RE.finditer(text):
            out.append(Finding("DOB", m.start(1), m.end(1), m.group(1)))
    if want("SECRET"):
        out.extend(find_secrets(text))
    out.sort(key=lambda f: (f.start, -f.end))
    # drop overlaps (keep earliest/longest)
    res: list[Finding] = []
    for f in out:
        if res and f.start < res[-1].end:
            continue
        res.append(f)
    return res


def redact(text: str, findings: list[Finding]) -> str:
    out, last = [], 0
    for f in findings:
        out.append(text[last:f.start])
        out.append(TOKENS.get(f.kind, f"[{f.kind}_REDACTED]"))
        last = f.end
    out.append(text[last:])
    return "".join(out)


def presidio_extra(text: str) -> list[Finding]:
    """Optional Presidio (PERSON, LOCATION, UK_NHS...). VERIFY AGAINST DOCS: presidio-analyzer API; not installed by default."""
    try:
        from presidio_analyzer import AnalyzerEngine  # type: ignore
    except Exception:  # noqa: BLE001
        return []
    eng = AnalyzerEngine()
    res = eng.analyze(text=text, language="en", entities=["PERSON", "UK_NHS", "CRYPTO"])
    return [Finding("PERSON" if r.entity_type == "PERSON" else r.entity_type, r.start, r.end, text[r.start:r.end]) for r in res if r.score >= 0.6]
