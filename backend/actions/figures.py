"""Extract and normalise figures (percentages, money, dates) and compare with approved data."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from . import dataref

MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"], 1)}
MONTHS.update({k[:3]: v for k, v in list(MONTHS.items())})
MONTHS["sept"] = 9

PCT_RE = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)\s*(?:%|per\s?cent\b|percent\b)", re.I)
MONEY_RE = re.compile(
    r"(?P<cur>£|\$|€|\bGBP\b|\bUSD\b|\bEUR\b)\s?(?P<n>\d[\d,]*(?:\.\d+)?)\s*(?P<mult>billion|bn|million|mn|m|thousand|k)?\b(?![\w])"
    r"|(?P<n2>\d[\d,]*(?:\.\d+)?)\s*(?P<mult2>billion|million|thousand)?\s*(?P<cur2>pounds|GBP|dollars|USD|euros|EUR)\b",
    re.I,
)
_MONTH_NAMES = "|".join(sorted(MONTHS, key=len, reverse=True))
DATE_RES = [
    re.compile(r"\b(?P<y>\d{4})-(?P<m>\d{2})-(?P<d>\d{2})\b"),
    re.compile(rf"\b(?P<d>\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?(?P<mn>{_MONTH_NAMES})\.?,?\s+(?P<y>\d{{4}})\b", re.I),
    re.compile(rf"\b(?P<mn>{_MONTH_NAMES})\.?\s+(?P<d>\d{{1,2}})(?:st|nd|rd|th)?,?\s+(?P<y>\d{{4}})\b", re.I),
]
MULT = {"billion": 1e9, "bn": 1e9, "million": 1e6, "mn": 1e6, "m": 1e6, "thousand": 1e3, "k": 1e3}
CUR = {"£": "gbp", "gbp": "gbp", "pounds": "gbp", "$": "usd", "usd": "usd", "dollars": "usd", "€": "eur", "eur": "eur", "euros": "eur"}


@dataclass
class Figure:
    unit: str  # pct | gbp | usd | eur | date
    value: float | str
    start: int
    end: int
    text: str


def extract_figures(text: str) -> list[Figure]:
    out: list[Figure] = []
    taken: list[tuple[int, int]] = []

    def free(s: int, e: int) -> bool:
        return not any(s < b and a < e for a, b in taken)

    for rx in DATE_RES:
        for m in rx.finditer(text):
            g = m.groupdict()
            mo = int(g["m"]) if g.get("m") else MONTHS.get(g["mn"].lower().rstrip("."))
            try:
                iso = date(int(g["y"]), mo, int(g["d"])).isoformat()
            except (TypeError, ValueError):
                continue
            if free(m.start(), m.end()):
                out.append(Figure("date", iso, m.start(), m.end(), m.group()))
                taken.append((m.start(), m.end()))
    for m in PCT_RE.finditer(text):
        if free(m.start(), m.end()):
            out.append(Figure("pct", float(m.group(1)), m.start(), m.end(), m.group()))
            taken.append((m.start(), m.end()))
    for m in MONEY_RE.finditer(text):
        if not free(m.start(), m.end()):
            continue
        n = m.group("n") or m.group("n2")
        cur = (m.group("cur") or m.group("cur2")).lower()
        mult = (m.group("mult") or m.group("mult2") or "").lower()
        val = float(n.replace(",", "")) * MULT.get(mult, 1)
        out.append(Figure(CUR[cur], val, m.start(), m.end(), m.group()))
        taken.append((m.start(), m.end()))
    out.sort(key=lambda f: f.start)
    return out


def approved_facts() -> list[dict]:
    return dataref.products()["facts"]


def approved_set() -> set[tuple[str, float | str]]:
    s: set[tuple[str, float | str]] = set()
    for f in approved_facts():
        s.add((f["unit"], round(float(f["value"]), 4)))
        if f.get("as_of"):
            s.add(("date", f["as_of"]))
    for d in dataref.products().get("extra_dates", []):
        s.add(("date", d))
    return s


def is_supported(fig: Figure, approved: set, context_figs: set) -> bool:
    key = (fig.unit, fig.value if fig.unit == "date" else round(float(fig.value), 4))
    if key in approved or key in context_figs:
        return True
    if fig.unit == "pct" and fig.value in (0, 100):
        return True
    if fig.unit in ("gbp", "usd", "eur") and fig.value < 1:
        return True
    return False


def fmt(unit: str, value: float) -> str:
    if unit == "pct":
        return f"{value:g}%"
    if value >= 1e9:
        return f"£{value / 1e9:g} billion"
    if value >= 1e6:
        return f"£{value / 1e6:g} million"
    return f"£{value:,.2f}".replace(".00", "")
