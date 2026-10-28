export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/admin/v1${path}`, {
    ...options, credentials: 'include', headers: { 'Content-Type': 'application/json', 'X-Tollgate-Admin': '1', ...options.headers },
  });
  if (response.status === 401 && !path.includes('/auth/')) {
    window.location.assign(new URL('/login', window.location.origin).href);
    throw new Error('Session expired. Please sign in.');
  }
  const data = await response.json();
  if (!response.ok) {
    const detail = data.detail;
    throw new Error(typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map((d: {msg: string}) => d.msg).join('; ') : 'Something went wrong. Please retry.');
  }
  return data as T;
}
export const money = (n: number, digits = 2) => new Intl.NumberFormat('en-US', {style: 'currency', currency: 'USD', maximumFractionDigits: digits}).format(n / 1e6);
export const number = (n: number) => new Intl.NumberFormat('en-US', {notation: n >= 10000 ? 'compact' : 'standard', maximumFractionDigits: 1}).format(n);
export interface Customer {id: string; name: string; display_name: string; plan: string; budget_override: number | null; spend: number; budget: number; ratio: number; tier: number; status: string; created_at: string}
export interface Step {at: number; tier: number}
export interface Plan {id: string; name: string; monthly_budget: number; rpm: number; degradation: Step[]; on_exhausted: string; overage_cap: number; pii_mode: string; pii_block_categories: string[]}
export interface Alias {id: string; name: string; allow_degrade: boolean; tiers: string[][]}
export interface Key {id: string; name: string; prefix: string; created_at: string; revoked_at: string | null; key?: string}
export interface Provider {name: string; configured: boolean; source: string; models: string[]}
export interface Tenant {id: string; name: string; display_name: string; rpm: number; default_plan: string}
export interface Log {id: string; customer_id: string; alias: string; model: string; provider: string; tier_served: number; status: string; http_status: number; input_tokens: number; output_tokens: number; cost: number; latency_ms: number; ttft_ms?: number; cache_hit: boolean; pii_counts: Record<string, number>; fallback_count: number; created_at: string; tokens_estimated: boolean}
export interface Daily {day: string; customer_id: string; requests: number; cost: number}
export interface Usage {requests: number; cost: number; pii_protected: number; cache_hits: number; avg_latency_ms: number; errors: number; daily: Daily[]; recent: Log[]; sampled: boolean}
