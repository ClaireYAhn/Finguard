"""Text helpers: normalisation, sentence splitting, negation, masking."""
from __future__ import annotations

import re
import unicodedata

ZERO_WIDTH = dict.fromkeys(map(ord, "​‌‍‎‏⁠⁡⁢⁣﻿­‪‫‬‭‮"), None)
CURLY = {ord("‘"): "'", ord("’"): "'", ord("“"): '"', ord("”"): '"', ord("–"): "-", ord("—"): "-"}
# small homoglyph table (Cyrillic/Greek look-alikes -> latin)
HOMOGLYPH = {ord(k): v for k, v in {
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "у": "y", "х": "x", "і": "i", "ѕ": "s", "ј": "j",
    "ɡ": "g", "ο": "o", "ρ": "p", "ν": "v", "α": "a", "ε": "e", "ι": "i",
}.items()}


def has_zero_width(text: str) -> bool:
    return any(ord(c) in ZERO_WIDTH for c in text)


def normalise(text: str) -> str:
    """Fold for matching: strip zero-width, NFKC, curly quotes, homoglyphs, lowercase, collapse spaces."""
    t = text.translate(ZERO_WIDTH)
    t = unicodedata.normalize("NFKC", t)
    t = t.translate(CURLY).translate(HOMOGLYPH).lower()
    return re.sub(r"\s+", " ", t)


_SENT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z£$€\"'(\[\d•*-])|\n+")


def split_sentences(text: str) -> list[str]:
    """Split on sentence ends followed by whitespace+capital; decimals like 4.6% never split."""
    return [s for s in _SENT_RE.split(text) if s and s.strip()]


NEG_RE = re.compile(
    r"\b(not|no|never|cannot|can't|cant|won't|wouldn't|shouldn't|don't|doesn't|isn't|aren't|without|unable|nothing|n't)\b|n't\b",
    re.I,
)


def negated_before(text: str, start: int, window: int = 40) -> bool:
    """True if a negation word appears within `window` chars before `start` in the same clause."""
    pre = text[max(0, start - window):start]
    pre = re.split(r"[.;:!?\n]", pre)[-1]
    return bool(NEG_RE.search(pre))


def mask(value: str, kind: str = "") -> str:
    """Masked evidence: never keeps the raw value (last 2-4 chars at most)."""
    v = re.sub(r"\s+", "", value)
    n = len(v)
    keep = 4 if kind == "CARD" else 2 if n > 8 else 0
    tail = v[-keep:] if keep else ""
    return f"{kind or 'VALUE'}:{'*' * max(n - keep, 1)}{tail}(len={n})"


def snippet(text: str, start: int, end: int, pad: int = 25) -> str:
    return text[max(0, start - pad):min(len(text), end + pad)].replace("\n", " ")


def is_definitional(text: str) -> bool:
    """'what is X' / 'explain X' style questions about a concept."""
    return bool(re.match(r"\s*(what\s+(is|are|does)|define|explain|how\s+does|can you explain|meaning of|tell me about)\b", text.lower()))
