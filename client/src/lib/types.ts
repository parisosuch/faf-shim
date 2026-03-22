export interface ShimRule {
  id: number;
  shim_id: number;
  order: number;
  field: string;
  operator: string;
  value: string;
  target_url: string;
  body_template: string | null;
}

export interface ShimVariable {
  id: number;
  shim_id: number;
  key: string;
  value: string;
}

export interface Shim {
  id: number;
  name: string;
  slug: string;
  target_url: string;
  headers: string;
  secret: string | null;
  signature_header: string | null;
  signature_algorithm: string | null;
  body_template: string | null;
  sample_payload: string | null;
  max_body_size_kb: number | null;
  log_retention_days: number | null;
  rate_limit_requests: number | null;
  rate_limit_window_seconds: number | null;
  created_at: string;
  rules: ShimRule[];
  variables: ShimVariable[];
}

export interface ShimExport {
  name: string;
  slug: string;
  target_url: string;
  headers: string;
  secret: string | null;
  signature_header: string | null;
  signature_algorithm: string | null;
  body_template: string | null;
  sample_payload: string | null;
  max_body_size_kb: number | null;
  log_retention_days: number | null;
  rate_limit_requests: number | null;
  rate_limit_window_seconds: number | null;
  rules: Omit<ShimRule, "id" | "shim_id">[];
  variables: Omit<ShimVariable, "id" | "shim_id">[];
}
