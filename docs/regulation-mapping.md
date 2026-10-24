# Regulation mapping

> **Illustrative, not legal advice.** This file is generated from `backend/policies/packs/*.yaml` by `python -m scripts.gen_regulation_mapping`. It explains why each control is *relevant* to a regulation. It does not state that using FinGuard makes a firm compliant. Article and rule numbers should be checked against the current text by qualified compliance staff.

Regimes referenced: UK GDPR and GDPR; EU AI Act (transparency, human oversight, logging, high-risk uses such as credit scoring); DORA (operational resilience, third-party ICT risk); MiFID II; FCA rules including Consumer Duty (PRIN 2A) and COBS; UK and EU market abuse regulation (MAR); SEC Marketing Rule; AML and financial-crime rules (POCA 2002, MLR 2017, EU AMLD); SR 11-7.

## 1. Rule to regulation

### IN-01 - Sensitive data redaction

*Stage:* Input &middot; *Default severity:* high &middot; *Default action:* modify

Redact card numbers, IBANs, sort codes, account numbers, NI/SSN numbers, emails, phones, dates of birth and secrets before text reaches the model.

| Regulation (illustrative) | Why it maps |
|---|---|
| UK GDPR Art. 5(1)(c) | Data minimisation: the external model should only receive personal data it needs. |
| GDPR Art. 25 | Data protection by design and by default is implemented by redacting before transmission. |
| DORA Art. 28 | Sending data to a third-party ICT provider (the model vendor) is a third-party risk to control. |

*Enabled in packs:* client_facing, coding_assistant, compliance_ops, credit_decision, doc_summariser, email_drafting, general_agent, internal_staff, kyc_extractor, research_copilot

### IN-02 - Prompt injection and jailbreak

*Stage:* Input &middot; *Default severity:* high &middot; *Default action:* block

Detect direct and indirect prompt injection and jailbreak attempts, including obfuscated text and hidden instructions in pasted documents and tool results.

| Regulation (illustrative) | Why it maps |
|---|---|
| EU AI Act Art. 15 | High-risk systems must be resilient against attempts to alter their use or behaviour (cybersecurity and robustness). |
| DORA Art. 9 | ICT security tools and policies should prevent manipulation of critical systems. |
| SR 11-7 | Model risk management expects controls on inputs that could cause a model to be used outside intended behaviour. |

*Enabled in packs:* client_facing, coding_assistant, compliance_ops, credit_decision, doc_summariser, email_drafting, general_agent, internal_staff, kyc_extractor, research_copilot

### IN-03 - Topic and intent control

*Stage:* Dialogue &middot; *Default severity:* medium &middot; *Default action:* block

Keep each use case within its intended topics and politely redirect off-scope or illicit requests.

| Regulation (illustrative) | Why it maps |
|---|---|
| SR 11-7 | Models should be used within their documented intended purpose. |
| EU AI Act Art. 13 | Systems should be used in line with their stated intended purpose and instructions. |

*Enabled in packs:* client_facing, coding_assistant, compliance_ops, credit_decision, email_drafting, internal_staff, research_copilot

### IN-04 - MNPI screening

*Stage:* Input &middot; *Default severity:* high &middot; *Default action:* escalate

Screen for suspected material non-public information (MNPI); keep it away from the external model and refer it to Compliance.

| Regulation (illustrative) | Why it maps |
|---|---|
| UK MAR Art. 14 | Prohibits unlawful disclosure of inside information; sending it to an external service may be a disclosure. |
| EU MAR Art. 10 | Unlawful disclosure of inside information is prohibited except in the normal course of duties. |
| MiFID II Art. 16 | Firms must maintain controls to manage information flows and conflicts. |

*Enabled in packs:* client_facing, coding_assistant, compliance_ops, credit_decision, doc_summariser, email_drafting, general_agent, internal_staff, kyc_extractor, research_copilot

### IN-05 - Role-based access control

*Stage:* Retrieval &middot; *Default severity:* high &middot; *Default action:* block

Enforce role-based access to applications, documents and bulk data requests.

| Regulation (illustrative) | Why it maps |
|---|---|
| UK GDPR Art. 5(1)(f) | Personal data must be protected against unauthorised access (integrity and confidentiality). |
| DORA Art. 9 | Access control and least privilege are part of ICT protection and prevention. |
| FCA SYSC 4 | Firms need adequate systems and controls, including who can see what. |

*Enabled in packs:* client_facing, coding_assistant, compliance_ops, credit_decision, doc_summariser, email_drafting, general_agent, internal_staff, kyc_extractor, research_copilot

### OUT-01 - Promissory and misleading language

*Stage:* Output &middot; *Default severity:* high &middot; *Default action:* modify

Rewrite promissory or misleading language such as guaranteed returns or risk-free claims.

| Regulation (illustrative) | Why it maps |
|---|---|
| FCA COBS 4.2 | Communications must be fair, clear and not misleading. |
| FCA Consumer Duty (PRIN 2A) | Communications must support consumer understanding and avoid foreseeable harm. |
| SEC Marketing Rule (206(4)-1) | Prohibits untrue or unsubstantiated statements, including implied guarantees of results. |

*Enabled in packs:* client_facing, compliance_ops, credit_decision, email_drafting, research_copilot

### OUT-02 - Advice boundary

*Stage:* Output &middot; *Default severity:* high &middot; *Default action:* modify

Replace personalised investment recommendations with general information and a referral to a regulated adviser.

| Regulation (illustrative) | Why it maps |
|---|---|
| MiFID II Art. 25 | Personal recommendations require a suitability assessment that a chatbot has not done. |
| FCA COBS 9 | Suitability rules apply to advice and portfolio management. |
| FCA Consumer Duty (PRIN 2A) | Avoids foreseeable harm from unsuitable guidance. |

*Enabled in packs:* client_facing, email_drafting

### OUT-03 - Grounding of figures

*Stage:* Output &middot; *Default severity:* high &middot; *Default action:* modify

Check percentages, money amounts and dates against approved data; correct or remove unsupported figures.

| Regulation (illustrative) | Why it maps |
|---|---|
| FCA COBS 4.2 | Figures in communications must be accurate to avoid misleading clients. |
| SEC Marketing Rule (206(4)-1) | Performance and fee figures must be substantiated. |
| EU AI Act Art. 15 | Accuracy of outputs is a requirement for high-risk systems. |
| SR 11-7 | Ongoing monitoring and outcomes analysis of model outputs. |

*Enabled in packs:* client_facing, credit_decision, doc_summariser, email_drafting, internal_staff, research_copilot

### OUT-04 - Source citation requirement

*Stage:* Output &middot; *Default severity:* medium &middot; *Default action:* modify

Research outputs with factual claims must cite approved source documents.

| Regulation (illustrative) | Why it maps |
|---|---|
| FCA COBS 12 | Investment research must be identifiable, sourced and clearly presented. |
| UK MAR Art. 20 | Recommendations must disclose sources and be presented objectively. |
| SEC Marketing Rule (206(4)-1) | Claims need a reasonable basis that can be evidenced. |

*Enabled in packs:* research_copilot

### OUT-05 - Required disclosures

*Stage:* Output &middot; *Default severity:* low &middot; *Default action:* modify

Append required disclosures once (idempotent).

| Regulation (illustrative) | Why it maps |
|---|---|
| EU AI Act Art. 50 | People must be told they are interacting with an AI system / AI-generated content. |
| FCA COBS 4.6 | Past-performance communications need prescribed warnings. |
| SEC Marketing Rule (206(4)-1) | Performance presentations require disclosures. |

*Enabled in packs:* client_facing, credit_decision, doc_summariser, research_copilot

### OUT-06 - Vulnerability and distress detection

*Stage:* Output &middot; *Default severity:* high &middot; *Default action:* escalate

Detect vulnerability and distress in the customer's messages, answer supportively and alert a human.

| Regulation (illustrative) | Why it maps |
|---|---|
| FCA FG21/1 | Guidance on the fair treatment of vulnerable customers requires recognising and supporting vulnerability. |
| FCA Consumer Duty (PRIN 2A) | The consumer support outcome requires help that meets vulnerable customers' needs. |
| EU AI Act Art. 14 | Human oversight: a person must be able to step in. |

*Enabled in packs:* client_facing, compliance_ops, email_drafting

### OUT-07 - Confidentiality and PII leakage

*Stage:* Output &middot; *Default severity:* high &middot; *Default action:* modify

Prevent leakage of personal data, secrets, restricted documents and the system prompt in model output.

| Regulation (illustrative) | Why it maps |
|---|---|
| UK GDPR Art. 5(1)(f) | Output must not expose personal data to people who should not see it. |
| UK GDPR Art. 32 | Appropriate technical measures protect confidentiality of processing. |
| DORA Art. 9 | Prevent loss of confidentiality of data in ICT systems. |

*Enabled in packs:* client_facing, coding_assistant, compliance_ops, credit_decision, doc_summariser, email_drafting, general_agent, internal_staff, kyc_extractor, research_copilot

### OUT-08 - Fairness screen

*Stage:* Output &middot; *Default severity:* high &middot; *Default action:* escalate

Flag decision reasoning that relies on protected characteristics.

| Regulation (illustrative) | Why it maps |
|---|---|
| Equality Act 2010 s.29 | Providers of services must not discriminate on protected characteristics. |
| UK GDPR Art. 22 | Restricts solely automated decisions with significant effects and use of special-category data. |
| EU AI Act Art. 10 | Data governance and bias examination for high-risk systems such as credit scoring. |
| FCA Consumer Duty (PRIN 2A) | Customers with protected characteristics must achieve good outcomes. |

*Enabled in packs:* credit_decision

### OUT-09 - AML tipping-off protection

*Stage:* Output &middot; *Default severity:* high &middot; *Default action:* escalate

Stop customer-facing drafts that reveal AML/SAR suspicion (tipping-off).

| Regulation (illustrative) | Why it maps |
|---|---|
| POCA 2002 s.333A | Disclosing that a suspicious activity report has been made, in a way likely to prejudice an investigation, is an offence. |
| MLR 2017 | Firms must have AML policies and controls, including staff handling of suspicion. |
| EU AMLD (2015/849) Art. 39 | Prohibition of disclosure to the customer concerned. |

*Enabled in packs:* compliance_ops, email_drafting

### OUT-10 - Explainability of decisions

*Stage:* Output &middot; *Default severity:* high &middot; *Default action:* escalate

Decision-support outputs must list the factors relied on.

| Regulation (illustrative) | Why it maps |
|---|---|
| EU AI Act Annex III(5)(b) | Creditworthiness assessment of natural persons is a high-risk use. |
| EU AI Act Art. 13 | High-risk systems must be transparent enough for users to interpret their output. |
| UK GDPR Art. 22 | Individuals subject to automated decisions are entitled to meaningful information about the logic. |
| SR 11-7 | Model outputs must be explainable to validators and users. |

*Enabled in packs:* credit_decision

### OUT-11 - Code safety

*Stage:* Output &middot; *Default severity:* high &middot; *Default action:* modify

Flag hard-coded secrets, credentials and client data in generated code or commit messages.

| Regulation (illustrative) | Why it maps |
|---|---|
| UK GDPR Art. 32 | Secrets and personal data in code repositories are a security-of-processing risk. |
| DORA Art. 9 | Credential and secrets hygiene is part of ICT protection. |
| DORA Art. 28 | Code sent to third-party services must not leak credentials to them. |

*Enabled in packs:* coding_assistant, general_agent

### TL-01 - PII or MNPI in tool arguments

*Stage:* Tool &middot; *Default severity:* high &middot; *Default action:* modify

Redact PII in tool-call arguments and hold calls that carry MNPI.

| Regulation (illustrative) | Why it maps |
|---|---|
| UK GDPR Art. 5(1)(c) | Tools should only receive the personal data they need. |
| UK MAR Art. 14 | Passing inside information to a tool or recipient may be unlawful disclosure. |

*Enabled in packs:* client_facing, coding_assistant, compliance_ops, credit_decision, doc_summariser, email_drafting, general_agent, internal_staff, kyc_extractor, research_copilot

### TL-02 - Bulk export and exfiltration

*Stage:* Tool &middot; *Default severity:* high &middot; *Default action:* block

Block bulk data export and exfiltration patterns.

| Regulation (illustrative) | Why it maps |
|---|---|
| UK GDPR Art. 32 | Prevents a hijacked agent from mass-extracting personal data. |
| DORA Art. 9 | Data-loss prevention is part of ICT protection. |

*Enabled in packs:* client_facing, coding_assistant, compliance_ops, credit_decision, doc_summariser, email_drafting, general_agent, internal_staff, kyc_extractor, research_copilot

### TL-03 - Role and tool access

*Stage:* Tool &middot; *Default severity:* high &middot; *Default action:* block

Enforce the application's tool allow/deny lists and role-based tool and data access.

| Regulation (illustrative) | Why it maps |
|---|---|
| DORA Art. 9 | Least-privilege access to ICT functions. |
| EU AI Act Art. 14 | Limits what an AI system can do without oversight. |

*Enabled in packs:* client_facing, coding_assistant, compliance_ops, credit_decision, doc_summariser, email_drafting, general_agent, internal_staff, kyc_extractor, research_copilot

### TL-04 - Injection text in tool arguments

*Stage:* Tool &middot; *Default severity:* high &middot; *Default action:* block

Block tool calls carrying injection text in arguments or recent context.

| Regulation (illustrative) | Why it maps |
|---|---|
| EU AI Act Art. 15 | Resilience against manipulation of an agent's behaviour. |
| SR 11-7 | Control over model use outside intended behaviour. |

*Enabled in packs:* client_facing, coding_assistant, compliance_ops, credit_decision, doc_summariser, email_drafting, general_agent, internal_staff, kyc_extractor, research_copilot

### TL-05 - Outbound destination allow-list

*Stage:* Tool &middot; *Default severity:* high &middot; *Default action:* block

Outbound tools (email, HTTP, upload) may only target allow-listed destinations.

| Regulation (illustrative) | Why it maps |
|---|---|
| DORA Art. 28 | Data leaving to unapproved third parties is a third-party ICT risk. |
| UK GDPR Art. 5(1)(f) | Prevents unauthorised disclosure of personal data. |

*Enabled in packs:* client_facing, coding_assistant, compliance_ops, credit_decision, doc_summariser, email_drafting, general_agent, internal_staff, kyc_extractor, research_copilot

### TL-06 - High-impact action approval

*Stage:* Tool &middot; *Default severity:* high &middot; *Default action:* escalate

Payments and account changes require human approval before execution.

| Regulation (illustrative) | Why it maps |
|---|---|
| EU AI Act Art. 14 | Human oversight of consequential actions. |
| SR 11-7 | Controls and limits on model-driven actions. |
| FCA SYSC 4 | Authorisation controls for money movement. |

*Enabled in packs:* client_facing, coding_assistant, compliance_ops, credit_decision, doc_summariser, email_drafting, general_agent, internal_staff, kyc_extractor, research_copilot

### TR-01 - Injection in tool results

*Stage:* Tool &middot; *Default severity:* high &middot; *Default action:* block

Scan tool results for hidden instructions (indirect prompt injection) before they return to the model.

| Regulation (illustrative) | Why it maps |
|---|---|
| EU AI Act Art. 15 | Resilience against indirect manipulation via data the system reads. |
| DORA Art. 9 | Treat external content as untrusted input. |

*Enabled in packs:* client_facing, coding_assistant, compliance_ops, credit_decision, doc_summariser, email_drafting, general_agent, internal_staff, kyc_extractor, research_copilot

### TR-02 - Restricted data in tool results

*Stage:* Tool &middot; *Default severity:* high &middot; *Default action:* block

Withhold tool results containing data the acting role may not see.

| Regulation (illustrative) | Why it maps |
|---|---|
| UK GDPR Art. 5(1)(f) | Confidentiality of personal data. |
| UK MAR Art. 10 | Inside information must not reach people without a need to know. |

*Enabled in packs:* client_facing, coding_assistant, compliance_ops, credit_decision, doc_summariser, email_drafting, general_agent, internal_staff, kyc_extractor, research_copilot

## 2. Regulation to rules

| Regulation (illustrative) | Rules | Why |
|---|---|---|
| DORA Art. 28 | IN-01, OUT-11, TL-05 | Sending data to a third-party ICT provider (the model vendor) is a third-party risk to control. |
| DORA Art. 9 | IN-02, IN-05, OUT-07, OUT-11, TL-02, TL-03, TR-01 | ICT security tools and policies should prevent manipulation of critical systems. |
| EU AI Act Annex III(5)(b) | OUT-10 | Creditworthiness assessment of natural persons is a high-risk use. |
| EU AI Act Art. 10 | OUT-08 | Data governance and bias examination for high-risk systems such as credit scoring. |
| EU AI Act Art. 13 | IN-03, OUT-10 | Systems should be used in line with their stated intended purpose and instructions. |
| EU AI Act Art. 14 | OUT-06, TL-03, TL-06 | Human oversight: a person must be able to step in. |
| EU AI Act Art. 15 | IN-02, OUT-03, TL-04, TR-01 | High-risk systems must be resilient against attempts to alter their use or behaviour (cybersecurity and robustness). |
| EU AI Act Art. 50 | OUT-05 | People must be told they are interacting with an AI system / AI-generated content. |
| EU AMLD (2015/849) Art. 39 | OUT-09 | Prohibition of disclosure to the customer concerned. |
| EU MAR Art. 10 | IN-04 | Unlawful disclosure of inside information is prohibited except in the normal course of duties. |
| Equality Act 2010 s.29 | OUT-08 | Providers of services must not discriminate on protected characteristics. |
| FCA COBS 12 | OUT-04 | Investment research must be identifiable, sourced and clearly presented. |
| FCA COBS 4.2 | OUT-01, OUT-03 | Communications must be fair, clear and not misleading. |
| FCA COBS 4.6 | OUT-05 | Past-performance communications need prescribed warnings. |
| FCA COBS 9 | OUT-02 | Suitability rules apply to advice and portfolio management. |
| FCA Consumer Duty (PRIN 2A) | OUT-01, OUT-02, OUT-06, OUT-08 | Communications must support consumer understanding and avoid foreseeable harm. |
| FCA FG21/1 | OUT-06 | Guidance on the fair treatment of vulnerable customers requires recognising and supporting vulnerability. |
| FCA SYSC 4 | IN-05, TL-06 | Firms need adequate systems and controls, including who can see what. |
| GDPR Art. 25 | IN-01 | Data protection by design and by default is implemented by redacting before transmission. |
| MLR 2017 | OUT-09 | Firms must have AML policies and controls, including staff handling of suspicion. |
| MiFID II Art. 16 | IN-04 | Firms must maintain controls to manage information flows and conflicts. |
| MiFID II Art. 25 | OUT-02 | Personal recommendations require a suitability assessment that a chatbot has not done. |
| POCA 2002 s.333A | OUT-09 | Disclosing that a suspicious activity report has been made, in a way likely to prejudice an investigation, is an offence. |
| SEC Marketing Rule (206(4)-1) | OUT-01, OUT-03, OUT-04, OUT-05 | Prohibits untrue or unsubstantiated statements, including implied guarantees of results. |
| SR 11-7 | IN-02, IN-03, OUT-03, OUT-10, TL-04, TL-06 | Model risk management expects controls on inputs that could cause a model to be used outside intended behaviour. |
| UK GDPR Art. 22 | OUT-08, OUT-10 | Restricts solely automated decisions with significant effects and use of special-category data. |
| UK GDPR Art. 32 | OUT-07, OUT-11, TL-02 | Appropriate technical measures protect confidentiality of processing. |
| UK GDPR Art. 5(1)(c) | IN-01, TL-01 | Data minimisation: the external model should only receive personal data it needs. |
| UK GDPR Art. 5(1)(f) | IN-05, OUT-07, TL-05, TR-02 | Personal data must be protected against unauthorised access (integrity and confidentiality). |
| UK MAR Art. 10 | TR-02 | Inside information must not reach people without a need to know. |
| UK MAR Art. 14 | IN-04, TL-01 | Prohibits unlawful disclosure of inside information; sending it to an external service may be a disclosure. |
| UK MAR Art. 20 | OUT-04 | Recommendations must disclose sources and be presented objectively. |

## 3. Packs

| Pack | Risk tier | Rules enabled |
|---|---|---|
| client_facing (Client-Facing Assistant) | limited | IN-01, IN-02, IN-03, IN-04, IN-05, OUT-01, OUT-02, OUT-03, OUT-05, OUT-06, OUT-07, TL-01, TL-02, TL-03, TL-04, TL-05, TL-06, TR-01, TR-02 |
| coding_assistant (Coding Assistant (Claude Code)) | minimal | IN-01, IN-02, IN-03, IN-04, IN-05, OUT-07, OUT-11, TL-01, TL-02, TL-03, TL-04, TL-05, TL-06, TR-01, TR-02 |
| compliance_ops (Compliance and Operations Copilot) | high | IN-01, IN-02, IN-03, IN-04, IN-05, OUT-01, OUT-06, OUT-07, OUT-09, TL-01, TL-02, TL-03, TL-04, TL-05, TL-06, TR-01, TR-02 |
| credit_decision (Credit Decision Support) | high | IN-01, IN-02, IN-03, IN-04, IN-05, OUT-01, OUT-03, OUT-05, OUT-07, OUT-08, OUT-10, TL-01, TL-02, TL-03, TL-04, TL-05, TL-06, TR-01, TR-02 |
| doc_summariser (Document Summariser) | limited | IN-01, IN-02, IN-04, IN-05, OUT-03, OUT-05, OUT-07, TL-01, TL-02, TL-03, TL-04, TL-05, TL-06, TR-01, TR-02 |
| email_drafting (Email Drafting Assistant) | limited | IN-01, IN-02, IN-03, IN-04, IN-05, OUT-01, OUT-02, OUT-03, OUT-06, OUT-07, OUT-09, TL-01, TL-02, TL-03, TL-04, TL-05, TL-06, TR-01, TR-02 |
| general_agent (General Agent) | high | IN-01, IN-02, IN-04, IN-05, OUT-07, OUT-11, TL-01, TL-02, TL-03, TL-04, TL-05, TL-06, TR-01, TR-02 |
| internal_staff (Internal Staff Assistant) | limited | IN-01, IN-02, IN-03, IN-04, IN-05, OUT-03, OUT-07, TL-01, TL-02, TL-03, TL-04, TL-05, TL-06, TR-01, TR-02 |
| kyc_extractor (KYC Data Extractor) | high | IN-01, IN-02, IN-04, IN-05, OUT-07, TL-01, TL-02, TL-03, TL-04, TL-05, TL-06, TR-01, TR-02 |
| research_copilot (Research Copilot) | limited | IN-01, IN-02, IN-03, IN-04, IN-05, OUT-01, OUT-03, OUT-04, OUT-05, OUT-07, TL-01, TL-02, TL-03, TL-04, TL-05, TL-06, TR-01, TR-02 |
