# FinGuard control-panel API contract

Base: same origin. In dev the Vite server proxies `/api` and `/v1` to `http://localhost:8000`. All `/api/*` calls except `/api/config`, `/api/auth/*`, `/api/healthz` need the admin session cookie (`fg_session`, set by login; use `credentials: "include"`). Errors: HTTP status + `{"detail": "friendly message"}` (FastAPI) - show `detail` to the user. 401 means "sign in again".

## Auth / config
- `GET /api/config` -> `{version, provider, mock, engine, store_raw, model_judge, public_url, banner, engine_status:{nemo_loaded,nemo_version,last_error}, signed_in, scope_note}`
- `POST /api/auth/login {password}` -> `{ok:true}` (401 on wrong password) ; `POST /api/auth/logout`

## Apps (use-case registry)
App object: `{id,name,owner,business_unit,description,risk_tier("minimal"|"limited"|"high"),eu_ai_act_note,model,data_classes[],policy_pack,allowed_roles[],default_role,tool_policy:{allowed_tools[],blocked_tools[],approval_required_tools[],allowed_outbound_domains[],tool_roles{}},enabled,created_at,key_prefix,template,is_demo}`
- `GET /api/apps` -> App[] each with extra `requests_7d, blocked_7d, last_activity (ISO|null)`
- `GET /api/templates` -> `[{key,name,description,risk_tier,eu_ai_act_note,model,data_classes,allowed_roles,default_role,tool_policy}]` (10 templates)
- `POST /api/apps` body = App fields (name required, policy_pack required) -> `{app, key, key_notice}`; **the full key is only returned here and by rotate** - show it once in a copy-able modal.
- `POST /api/apps/from-template {template,name?,owner?,business_unit?}` -> `{app,key,key_notice}`
- `PATCH /api/apps/{id}` partial App fields (incl. `enabled`) -> App ; `DELETE /api/apps/{id}` ; `POST /api/apps/{id}/rotate-key` -> `{app,key,key_notice}`
- `POST /api/apps/{id}/test {message, role?}` -> `{action,text,rules_fired[],trace:CheckResult[],audit_id,case_id,engine,latency,pack,headers,note}` (409 if app disabled)

CheckResult: `{rule_id,name,stage("input"|"dialogue"|"retrieval"|"output"|"tool"),status("pass"|"modified"|"blocked"|"escalated"),severity("low"|"medium"|"high"),explanation,regulations:[{ref,why}],evidence:string[],latency_ms,check_type("deterministic"|"pattern"|"model"),error|null}`

## Policies
- `GET /api/policies` -> `[{pack,title,version,risk_tier,rules_enabled,rules_total}]`
- `GET /api/policies/{pack}?version=N` -> `{pack,title,version,risk_tier,regulation_note,settings:{...},rules:[{id,name,description,stage,enabled,severity,action("allow"|"modify"|"block"|"escalate"|"log"),thresholds{},regulations:[{ref,why}]}]}`
- `PUT /api/policies/{pack} {pack:<full pack object>, note}` -> new version object (422 `detail` on invalid)
- `GET /api/policies/{pack}/history` -> `[{version,created_at,author,note}]` newest first
- `GET /api/policies/{pack}/diff?from=1&to=2` -> `{pack,from,to,unified:string,changes:[{rule_id,fields[],before{},after{}}]}`
- `POST /api/policies/{pack}/rollback {version}` -> new version object
All regulation mappings are "illustrative, not legal advice" - label them so in the UI.

## Audit / live traffic
Audit record: `{id,ts,app_id,app_name,user,role,channel("gateway"|"tool-call"|"hook"|"demo"|"simulated"|"review"),original_input,redacted_input,raw_output,final_output,rule_results:CheckResult[],final_action("allow"|"modify"|"block"|"escalate"|"error"|"review_approved"|"review_rejected"),latency:{input_ms,model_ms,output_ms,total_ms,tool_ms},pack,pack_version,model,engine("nemo"|"native"|"off"|"n/a"),extra{},prev_hash,hash}`
- `GET /api/audit?app_id&action&rule&severity&channel&from=YYYY-MM-DD&to=YYYY-MM-DD&q&limit(<=1000)&offset` -> record[] newest first
- `GET /api/audit/{id}` -> record ; `GET /api/audit/verify` -> `{ok,count,head_hash,broken_at,audit_id,message}`
- `GET /api/audit/export?format=csv|json&<same filters>` -> file download (use a normal link/`window.location`)

## Review queue
Case: `{id,audit_id,app_id,app_name,kind("mnpi"|"vulnerability"|"tipping-off"|"fairness"|"explainability"|"tool_approval"|"content"),status("open"|"approved"|"rejected"),reason,rule_ids[],created_at,decided_at,reviewer_note,payload{input,proposed_output,final_output | agent_id,tool,arguments,user,role},severity}`
- `GET /api/reviews?status=open&app_id` -> Case[] ; `POST /api/reviews/{id}/decide {decision:"approved"|"rejected", note}` -> Case (409 if already decided)

## Overview
`GET /api/overview?days=14` -> `{days, cards:{requests,blocked,modified,escalated,allowed,open_reviews,apps_live,apps_idle,apps_total}, series:[{t,allow,modify,block,escalate,total}], bucket("hour"|"day"), per_app:[{app_id,app,tier,requests,blocked,modified,escalated,violation_rate}], per_rule:[{rule_id,name,fired,modified,blocked,escalated}], top_rules, heatmap:[{app,tier,requests,violation_rate}], attention:[{kind("rising_blocks"|"unreviewed_escalations"|"disabled_rules"|"no_activity"),app_id,app,detail}], simulated_requests, simulated_share, channels{}}`

## Reports
`GET /api/reports/{app_id}?from=YYYY-MM-DD&to=YYYY-MM-DD` -> printable HTML page (open in a new tab: `target=_blank`, cookie auth works).

## Seed / simulate
- `POST /api/seed` -> `{seeded,apps:[{template,app_id,name,key_prefix}],note}` (creates one demo app per template; safe to repeat)
- `POST /api/simulate {count(1-1000), days(0-30)}` -> `{sent,actions{},note}` real gateway traffic tagged channel=simulated (backdated timestamps; say so in the UI)

## Evaluation
- `POST /api/eval/run` (takes a few seconds) -> run object; `GET /api/eval/latest` -> run object | null
- run: `{id,ts,provider,model,mock,engine,dataset_items,note,results:{overall:{items,risky_items,legit_items,violation_rate_off,violation_rate_on,unsupported_figure_rate_off/on,figures_checked_off/on,pii_leakage_rate_off/on,injection_success_rate_off/on,mnpi_catch_rate_off/on,false_positive_rate_off/on,legit_modified_or_stopped_rate_off/on,avg_added_latency_ms,expected_action_match}, per_use_case:{<template>:{same keys as overall}}, per_rule:[{rule_id,expected,caught,unexpected_fires,recall}], audit:{decisions,records_written,complete_records,complete_share,chain_ok,chain_records}, mismatches:[{id,use_case,input,expected_action,actual_action,expected_categories,fired}], engines[]}, items:[{id,use_case,kind,expected_action,off_action,on_action,off_violation,on_violation,fired,input,on_output}]}`
- Rates are 0..1 floats or `null` when not applicable (show "n/a"). **Always show `run.model` and `run.note`** (mock results do not prove real-model performance).

## Demo
- `GET /api/demo/scenarios` -> `[{scenario_id,title,surface,use_case,input,without,with,role}]` (13)
- `POST /api/demo/run/{scenario_id}` ; `POST /api/demo/run-all` -> `{results:Result[],scorecard,provider,model}` ; `GET /api/demo/cache` -> `{results,scorecard|null,provider}`
- Result: `{scenario_id,title,surface,use_case,input,without_note,with_note,ran_at, off:Side, on:Side}`; Side: `{text,action,rules_fired[],trace:CheckResult[],latency_ms,harmful:boolean,audit_id,engine,model_received}`
- scorecard: `{scenarios,harmful_off,harmful_on,stopped_or_fixed,escalated_to_humans,avg_added_latency_ms}`
