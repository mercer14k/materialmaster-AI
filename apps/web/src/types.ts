export type Material = {
  material_id: string;
  source_system: string;
  description: string;
  material_group: string;
  manufacturer: string;
  manufacturer_part_number: string;
  base_uom: string;
  order_uom: string;
  order_to_base_factor: string | null;
  unit_price: string | null;
  price_unit: string;
  currency: string;
  supplier_id: string | null;
  purchasing_org: string | null;
  lead_time_days: number | null;
  lifecycle: string;
  procurement_blocked: boolean;
  ingested_at?: string;
  validation_status?: string;
};
export type Finding = {
  id: string;
  finding_id: string;
  kind: string;
  severity: string;
  material_ids: string[];
  title: string;
  evidence: Record<string, unknown>;
  proposed_action: string;
  method: string;
  score: number;
  status: string;
  version: number;
  learned_priority: number;
};
export type Detail = Finding & {
  records: {
    raw: Material;
    normalized: Material;
    dataset_id: string;
    ingested_at: string;
    validation_status: string;
  }[];
  reviews: { decision: string; reason: string; actor: string; at: string }[];
};
export type Page<T> = {
  items: T[];
  total: number;
  offset: number;
  limit: number;
};
export type Cohort = { total: number; affected: number; quality_score: number };
export type Metrics = {
  total_materials: number;
  affected_materials: number;
  quality_score: number | null;
  findings: number;
  by_kind: Record<string, number>;
  by_severity: Record<string, number>;
  by_group: Record<string, Cohort>;
  by_source: Record<string, Cohort>;
  invalid_rows: number;
  duration_seconds: number;
  algorithm_version: string;
  embedding_model: string;
  warning: string | null;
};
export type Overview = {
  dataset_id: string;
  dataset_name: string;
  status: string;
  metrics: Metrics;
  review_counts: Record<string, number>;
  feedback: {
    accepted: number;
    rejected: number;
    reviewed_pairs: number;
    posterior_acceptance: number;
  };
  history: (Metrics & { at: string })[];
};
export type Dataset = {
  id: string;
  name: string;
  total: number;
  valid: number;
  invalid: number;
  status: string;
  created_at: string;
};
export type Audit = {
  id: number;
  action: string;
  actor: string;
  entity_id: string;
  trace_id: string;
  at: string;
  data: Record<string, unknown>;
};
export type Plan = {
  id: string;
  kind: string;
  severity: string;
  material_ids: string[];
  action: string;
  review_status: string;
  owner_role: string;
};
