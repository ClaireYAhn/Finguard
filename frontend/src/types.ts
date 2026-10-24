export type Json = any

export interface Regulation { ref: string; why: string }
export interface CheckResult {
  rule_id: string
  name: string
  stage: string
  status: 'pass' | 'modified' | 'blocked' | 'escalated' | string
  severity: 'low' | 'medium' | 'high' | string
  explanation: string
  regulations: Regulation[]
  evidence: string[]
  latency_ms: number
  check_type: string
  error?: string | null
}
export interface ToolPolicy {
  allowed_tools: string[]
  blocked_tools: string[]
  approval_required_tools: string[]
  allowed_outbound_domains: string[]
  tool_roles: Record<string, string[]>
}
export interface App {
  id: string
  name: string
  owner: string
  business_unit: string
  description: string
  risk_tier: 'minimal' | 'limited' | 'high' | string
  eu_ai_act_note: string
  model: string
  data_classes: string[]
  policy_pack: string
  allowed_roles: string[]
  default_role: string
  tool_policy: ToolPolicy
  enabled: boolean
  created_at: string
  key_prefix: string
  template: string | null
  is_demo: boolean
  requests_7d?: number
  blocked_7d?: number
  last_activity?: string | null
}
export interface Template {
  key: string
  name: string
  description: string
  risk_tier: string
  eu_ai_act_note: string
  model: string
  data_classes: string[]
  allowed_roles: string[]
  default_role: string
  tool_policy: ToolPolicy
}
export interface Config {
  version: string
  provider: string
  mock: boolean
  engine: string
  store_raw: boolean
  model_judge: boolean
  public_url: string
  banner: string
  engine_status: { nemo_loaded: boolean; nemo_version: string | null; last_error: string | null }
  signed_in: boolean
  scope_note: string
}
export interface AuditRecord {
  id: string
  ts: string
  app_id: string
  app_name: string
  user: string
  role: string
  channel: string
  original_input: string
  redacted_input: string
  raw_output: string
  final_output: string
  rule_results: CheckResult[]
  final_action: string
  latency: { input_ms?: number; model_ms?: number; output_ms?: number; total_ms?: number; tool_ms?: number }
  pack: string
  pack_version: number
  model: string
  engine: string
  extra: Record<string, Json>
  prev_hash: string
  hash: string
}
export interface ReviewCase {
  id: string
  audit_id: string
  app_id: string
  app_name: string
  kind: string
  status: 'open' | 'approved' | 'rejected'
  reason: string
  rule_ids: string[]
  created_at: string
  decided_at: string | null
  reviewer_note: string | null
  payload: Record<string, Json>
  severity: string
}
export interface PolicyRule {
  id: string
  name: string
  description: string
  stage: string
  enabled: boolean
  severity: string
  action: string
  thresholds: Record<string, Json>
  regulations: Regulation[]
}
export interface PolicyPack {
  pack: string
  title: string
  version: number
  risk_tier: string
  regulation_note: string
  settings: Record<string, Json>
  rules: PolicyRule[]
}
export interface Overview {
  days: number
  cards: Record<string, number>
  series: { t: string; allow: number; modify: number; block: number; escalate: number; total: number }[]
  bucket: string
  per_app: { app_id: string; app: string; tier: string; requests: number; blocked: number; modified: number; escalated: number; violation_rate: number }[]
  per_rule: { rule_id: string; name: string; fired: number; modified: number; blocked: number; escalated: number }[]
  top_rules: Json
  heatmap: { app: string; tier: string; requests: number; violation_rate: number }[]
  attention: { kind: string; app_id: string; app: string; detail: string }[]
  simulated_requests: number
  simulated_share: number
  channels: Record<string, number>
}
export interface DemoSide {
  text: string
  action: string
  rules_fired: string[]
  trace: CheckResult[]
  latency_ms: number
  harmful: boolean
  audit_id: string
  engine: string
  model_received: string
}
export interface DemoResult {
  scenario_id: string
  title: string
  surface: string
  use_case: string
  input: string
  without_note: string
  with_note: string
  ran_at: string
  off: DemoSide
  on: DemoSide
}
export interface Scorecard {
  scenarios: number
  harmful_off: number
  harmful_on: number
  stopped_or_fixed: number
  escalated_to_humans: number
  avg_added_latency_ms: number
}
export interface DemoScenario { scenario_id: string; title: string; surface: string; use_case: string; input: string; without: string; with: string; role: string }
