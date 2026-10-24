"""Create demo apps (one per template). Keys are returned once; existing demo apps get a fresh key so the simulator can use them."""
from __future__ import annotations

from policies import store as policies
from registry import store as registry
from registry.templates import TEMPLATES

OWNERS = {"client_facing": ("Digital Channels", "Retail Banking"), "research_copilot": ("Research Desk", "Asset Management"), "compliance_ops": ("Financial Crime", "Compliance"),
          "internal_staff": ("People Technology", "Operations"), "coding_assistant": ("Platform Engineering", "Technology"), "doc_summariser": ("Operations Excellence", "Operations"),
          "kyc_extractor": ("Onboarding", "Operations"), "credit_decision": ("Credit Risk", "Lending"), "email_drafting": ("Client Services", "Retail Banking"), "general_agent": ("AI Lab", "Technology")}


def seed_demo_apps() -> dict[str, dict]:
    policies.seed_packs()
    out: dict[str, dict] = {}
    for key in TEMPLATES:
        app = registry.get_by_template(key)
        if app is None:
            owner, bu = OWNERS[key]
            app, raw = registry.create_from_template(key, owner=owner + " (fictional)", business_unit=bu, is_demo=True)
        else:
            app, raw = registry.rotate_key(app["id"])  # type: ignore[misc]
        out[key] = {"app_id": app["id"], "name": app["name"], "key": raw, "tier": app["risk_tier"]}
    return out
