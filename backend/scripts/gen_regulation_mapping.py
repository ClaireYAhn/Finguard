"""Generate docs/regulation-mapping.md from the YAML policy packs (single source of truth)."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT.parent / "docs" / "regulation-mapping.md"
STAGE_NAMES = {"input": "Input", "dialogue": "Dialogue", "retrieval": "Retrieval", "output": "Output", "tool": "Tool"}


def main() -> None:
    packs = {}
    for f in sorted((ROOT / "policies" / "packs").glob("*.yaml")):
        d = yaml.safe_load(f.read_text())
        packs[d["pack"]] = d
    rules: dict[str, dict] = {}
    enabled_in: dict[str, list[str]] = defaultdict(list)
    for key, p in packs.items():
        for r in p["rules"]:
            rules.setdefault(r["id"], r)
            if r["enabled"]:
                enabled_in[r["id"]].append(key)
    by_reg: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for rid, r in rules.items():
        for g in r["regulations"]:
            by_reg[g["ref"]].append((rid, g["why"]))

    L = ["# Regulation mapping", "",
         "> **Illustrative, not legal advice.** This file is generated from `backend/policies/packs/*.yaml` by `python -m scripts.gen_regulation_mapping`. "
         "It explains why each control is *relevant* to a regulation. It does not state that using FinGuard makes a firm compliant. Article and rule numbers should be checked "
         "against the current text by qualified compliance staff.", "",
         "Regimes referenced: UK GDPR and GDPR; EU AI Act (transparency, human oversight, logging, high-risk uses such as credit scoring); DORA (operational resilience, third-party ICT risk); "
         "MiFID II; FCA rules including Consumer Duty (PRIN 2A) and COBS; UK and EU market abuse regulation (MAR); SEC Marketing Rule; AML and financial-crime rules (POCA 2002, MLR 2017, EU AMLD); SR 11-7.", "",
         "## 1. Rule to regulation", ""]
    for rid, r in rules.items():
        L += [f"### {rid} - {r['name']}", "", f"*Stage:* {STAGE_NAMES.get(r['stage'], r['stage'])} &middot; *Default severity:* {r['severity']} &middot; *Default action:* {r['action']}", "", r["description"], "",
              "| Regulation (illustrative) | Why it maps |", "|---|---|"]
        L += [f"| {g['ref']} | {g['why']} |" for g in r["regulations"]]
        L += ["", f"*Enabled in packs:* {', '.join(enabled_in[rid]) or 'none'}", ""]
    L += ["## 2. Regulation to rules", "", "| Regulation (illustrative) | Rules | Why |", "|---|---|---|"]
    for ref in sorted(by_reg):
        L.append(f"| {ref} | {', '.join(sorted({x[0] for x in by_reg[ref]}))} | {by_reg[ref][0][1]} |")
    L += ["", "## 3. Packs", "", "| Pack | Risk tier | Rules enabled |", "|---|---|---|"]
    for key, p in packs.items():
        L.append(f"| {key} ({p['title']}) | {p['risk_tier']} | {', '.join(r['id'] for r in p['rules'] if r['enabled'])} |")
    L.append("")
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text("\n".join(L))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
