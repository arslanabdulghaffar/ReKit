export type Role = 'viewer' | 'intake' | 'reviewer' | 'planner' | 'approver' | 'executor';
export interface Actor { actor_id: string; kind: 'human' | 'service'; roles: Role[] }
export type Condition = 'unknown' | 'acceptable' | 'damaged';
export interface Identity { component_type_id: string; revision: string }
export interface Catalog {
  catalog_id: string; version: string; synthetic: boolean;
  families: { family_id: string; name: string; required_component_types: string[] }[];
  component_types: { component_type_id: string; family_id: string; name: string }[];
  revisions: Identity[];
  configurations: { configuration_id: string; family_id: string; version: string; bom: { component_type_id: string; quantity: number }[] }[];
  policies: { policy_id: string; version: string; configuration_id: string; approved_by: string; approved_at: string; rules: { component_type_id: string; allowed_revisions: string[]; allowed_conditions: Condition[] }[] }[];
}
export interface ReturnBatch { batch_id: string; received_at: string }
export interface ReturnRecord { return_id: string; batch_id: string; product_family_id: string; received_at: string; declared_configuration_id: string | null }
export interface PhysicalComponent { physical_component_id: string; source_return_id: string; registered_at: string }
export interface Observation { observation_id: string; physical_component_id: string; source_return_id: string; captured_at: string; evidence_reference: string; source: string; source_reference: string; visible_marking: string | null; visible_revision: string | null }
export interface Verification { verification_id: string; physical_component_id: string; identity: Identity; operator_id: string; verified_at: string; evidence_observation_ids: string[]; visible_condition: Condition; reason: string; supersedes_verification_id: string | null }
export interface CurrentEvidence { physical_component_id: string; version: number; state: 'unresolved' | 'review_required' | 'verified'; verification: Verification | null; unresolved_reasons: string[] }
export interface EvidenceHistory { component: PhysicalComponent; current: CurrentEvidence; events: { sequence: number; event_id: string; kind: string; recorded_at: string; payload: Record<string, unknown> }[] }
export interface InventoryItem { component: PhysicalComponent; evidence: CurrentEvidence; eligibility: 'held' | 'eligible' }
export interface InventoryEntry { item: InventoryItem; availability: 'available' | 'held' | 'reserved' | 'consumed'; plan_id: string | null; action_id: string | null }
export interface CompletedKit { completed_kit_id: string; plan_id: string; action_id: string; configuration_id: string; component_ids: string[]; operator_id: string; completed_at: string; evidence_references: string[] }
export interface InventorySnapshot { items: InventoryEntry[]; completed_kits: CompletedKit[] }
export interface ImageAsset { asset_id: string; physical_component_id: string; return_id: string; sha256: string; byte_size: number; media_type: string; width: number; height: number; received_at: string; uploaded_by: string; observation_id: string; availability: 'available' | 'missing' | 'corrupt' | 'unavailable' }
export interface UploadResult { asset: ImageAsset; observation: Observation; duplicate: boolean }
export interface EconomicScenario {
  scenario_id: string; description: string; currency: string; valuation_date: string;
  labor_cost_per_minute_cents: number; labor_capacity_minutes: number | null; scenario_estimate: true;
  kits: { configuration_id: string; selling_price_cents: number; labor_minutes: number; other_cost_cents: number; demand_limit: number | null }[];
  components: { physical_component_id: string; donor_value_cents: number; salvage_value_cents: number; salvage_labor_minutes: number }[];
  returns: { return_id: string; liquidation_value_cents: number; liquidation_labor_minutes: number }[];
}
export type ActionKind = 'rebuild' | 'liquidate' | 'salvage' | 'retain' | 'hold';
export interface RecoveryAction { action_id: string; kind: ActionKind; component_ids: string[]; configuration_id: string | null; source_return_id: string | null; labor_minutes: number; cash_recovery_cents: number; retained_value_cents: number; modeled_value_cents: number; donor_opportunity_cost_cents: number; incremental_vs_retain_cents: number; explanation: string[] }
export interface RecoveryPlan {
  plan_id: string; input_hash: string; status: string; selected_actions: RecoveryAction[];
  modeled_value_cents: number | null; cash_recovery_cents: number | null; retained_value_cents: number | null;
  labor_minutes: number | null; best_bound_cents: number | null; absolute_gap_cents: number | null;
  solver_version: string; worker_count: number; wall_time_seconds: number; number_of_candidates: number;
  explanations: string[]; rejections: { subject: string; reasons: string[] }[]; scenario_estimate: true;
  problem: { inventory: InventoryItem[]; scenario: EconomicScenario; catalog: Catalog; policy: { policy_id: string; version: string }; return_contents: { return_id: string; component_ids: string[] }[] };
}
export interface StoredPlan { plan: RecoveryPlan; version: number; state: 'proposed' | 'approved' | 'cancelled' | 'completed'; completed_action_ids: string[] }
export interface PlanSummary { plan_id: string; scenario_id: string; description: string; currency: string; version: number; state: StoredPlan['state']; status: string; modeled_value_cents: number | null; cash_recovery_cents: number | null; retained_value_cents: number | null; created_at: string }
export interface AuditRecord { sequence: number; plan_id: string; operation_id: string; operator_id: string; kind: string; plan_version: number; reason: string; recorded_at: string; action_id: string | null }
export interface WorkspaceData { catalog: Catalog; batches: ReturnBatch[]; returns: ReturnRecord[]; inventory: InventorySnapshot; plans: PlanSummary[] }
