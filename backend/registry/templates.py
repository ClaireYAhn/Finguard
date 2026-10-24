"""Use-case templates. Each has its own policy pack (see policies/packs)."""
from __future__ import annotations

from typing import Any

NB = "Northbridge Financial"
DOMAINS = ["northbridge-financial.example"]
GENERAL_TL = {"allowed_tools": [], "blocked_tools": [], "approval_required_tools": [], "allowed_outbound_domains": DOMAINS, "tool_roles": {}}

TEMPLATES: dict[str, dict[str, Any]] = {
    "client_facing": dict(name="Client-Facing Assistant", description=f"Answers retail client questions about {NB} products. Fictional firm.",
        risk_tier="limited", eu_ai_act_note="Limited risk: interacts directly with natural persons, so Art. 50 transparency applies. Becomes high risk if it starts deciding eligibility or credit.",
        model="claude-sonnet-5-5", data_classes=["client PII", "product data"], allowed_roles=["client", "adviser"], default_role="client",
        tool_policy={**GENERAL_TL, "allowed_tools": ["lookup_product_info", "get_branch_hours"], "blocked_tools": ["export_clients", "send_email"]}),
    "research_copilot": dict(name="Research Copilot", description="Helps analysts summarise internal research and fund data with citations.",
        risk_tier="limited", eu_ai_act_note="Limited risk: internal analyst productivity; outputs reviewed by humans before use. MAR and research rules still apply.",
        model="claude-sonnet-5-5", data_classes=["internal research", "fund data"], allowed_roles=["analyst", "adviser", "compliance"], default_role="analyst",
        tool_policy={**GENERAL_TL, "allowed_tools": ["search_research", "read_document"], "blocked_tools": ["send_email"]}),
    "compliance_ops": dict(name="Compliance and Operations Copilot", description="Supports KYC reviews, AML case notes and complaint handling.",
        risk_tier="high", eu_ai_act_note="Treated as high risk by the firm: touches AML decisions and customer outcomes. Human review of every decision is required.",
        model="claude-sonnet-5-5", data_classes=["client PII", "AML case data", "complaints"], allowed_roles=["compliance", "operations"], default_role="compliance",
        tool_policy={**GENERAL_TL, "allowed_tools": ["read_case", "draft_letter", "search_cases"], "approval_required_tools": ["close_case"]}),
    "internal_staff": dict(name="Internal Staff Assistant", description="General Q&A for employees about policies, products and processes.",
        risk_tier="limited", eu_ai_act_note="Limited risk: internal Q&A. Transparency and data protection duties apply.",
        model="claude-haiku-5-5", data_classes=["internal documents"], allowed_roles=["staff", "adviser", "analyst", "operations", "compliance", "developer"], default_role="staff",
        tool_policy={**GENERAL_TL, "allowed_tools": ["search_intranet"], "blocked_tools": ["export_clients"]}),
    "coding_assistant": dict(name="Coding Assistant (Claude Code)", description="Developer coding assistant used through Claude Code hooks and the gateway.",
        risk_tier="minimal", eu_ai_act_note="Minimal risk: internal developer tooling. Secrets and client data handling still matter.",
        model="claude-sonnet-5-5", data_classes=["source code"], allowed_roles=["developer"], default_role="developer",
        tool_policy={**GENERAL_TL, "allowed_tools": ["Read", "Edit", "Write", "Bash", "Grep", "Glob"], "blocked_tools": [], "approval_required_tools": [], "allowed_outbound_domains": DOMAINS + ["github.com", "pypi.org", "npmjs.com"]}),
    "doc_summariser": dict(name="Document Summariser", description="Summarises emails and documents; main risk is hidden instructions in the content.",
        risk_tier="limited", eu_ai_act_note="Limited risk: summarisation for staff; indirect prompt injection is the key control.",
        model="claude-haiku-5-5", data_classes=["emails", "documents"], allowed_roles=["staff", "operations", "compliance", "adviser", "analyst"], default_role="staff",
        tool_policy={**GENERAL_TL, "allowed_tools": ["read_document"], "blocked_tools": ["send_email", "http_post"]}),
    "kyc_extractor": dict(name="KYC Data Extractor", description="Extracts structured fields from onboarding documents. Handles personal data by design.",
        risk_tier="high", eu_ai_act_note="High risk by firm policy: affects onboarding decisions and handles identity data. Must run on an approved, contractually protected model.",
        model="claude-sonnet-5-5", data_classes=["identity documents", "client PII"], allowed_roles=["operations", "compliance"], default_role="operations",
        tool_policy={**GENERAL_TL, "allowed_tools": ["read_document", "write_kyc_record"], "approval_required_tools": ["approve_onboarding"]}),
    "credit_decision": dict(name="Credit Decision Support", description="Suggests credit decision outcomes for an underwriter, with reasons.",
        risk_tier="high", eu_ai_act_note="High risk: EU AI Act Annex III(5)(b) lists creditworthiness evaluation of natural persons. Requires human oversight, logging, bias testing.",
        model="claude-opus-5-5", data_classes=["client PII", "credit data"], allowed_roles=["operations", "compliance", "adviser"], default_role="operations",
        tool_policy={**GENERAL_TL, "allowed_tools": ["get_credit_file", "score_application"], "approval_required_tools": ["approve_loan", "decline_loan"]}),
    "email_drafting": dict(name="Email Drafting Assistant", description="Drafts emails to clients and colleagues for human review before sending.",
        risk_tier="limited", eu_ai_act_note="Limited risk: drafts only, a human sends. Tipping-off and promissory language are the main risks.",
        model="claude-sonnet-5-5", data_classes=["client PII"], allowed_roles=["staff", "adviser", "operations", "compliance"], default_role="staff",
        tool_policy={**GENERAL_TL, "allowed_tools": ["save_draft"], "blocked_tools": ["send_email"]}),
    "general_agent": dict(name="General Agent", description="Autonomous agent with tools (email, HTTP, payments). Every tool call goes through the agent guard.",
        risk_tier="high", eu_ai_act_note="High risk by firm policy: autonomous actions with financial effect need human oversight (Art. 14).",
        model="claude-sonnet-5-5", data_classes=["client PII", "internal documents"], allowed_roles=["agent", "staff", "operations"], default_role="agent",
        tool_policy={**GENERAL_TL, "allowed_tools": ["search_docs", "read_file", "send_email", "http_post", "lookup_client", "export_clients"], "blocked_tools": ["delete_database"], "approval_required_tools": ["create_payment", "close_account"]}),
}
