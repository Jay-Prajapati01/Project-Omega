import { api } from "./api";

export type Plan = { key: "free" | "plus" | "pro"; name: string; price_paise: number; currency: string; limits: Record<string, number> };
export type Entitlement = { role: "owner" | "admin" | "member"; base_plan: string; effective_plan: string; beta_tester: boolean; grants: { id: string; plan: string; cohort?: string; expires_at: string }[]; usage: Record<string, { used: number; limit: number; remaining: number }>; period: string; ai_mode: "managed" | "byok" };

export const getPlans = () => api.get<{ plans: Plan[] }>("/v1/public/plans").then((r) => r.data);
export const getEntitlement = () => api.get<Entitlement>("/v1/me/entitlements").then((r) => r.data);
export const getProviderKeys = () => api.get<{ keys: ProviderKey[]; preferences: ProviderPreference[] }>("/v1/me/provider-keys").then((r) => r.data);
export type ProviderKey = { provider: "groq" | "gemini"; masked_key: string; status: string; verified_at?: string };
export type ProviderPreference = { purpose: "llm" | "embeddings" | "transcription"; provider: "groq" | "gemini"; mode: "managed" | "byok"; fallback_to_managed: boolean };
export const saveProviderKey = (provider: "groq" | "gemini", key: string) => api.post(`/v1/me/provider-keys/${provider}`, { key }).then((r) => r.data);
export const deleteProviderKey = (provider: "groq" | "gemini") => api.delete(`/v1/me/provider-keys/${provider}`);
export const savePreferences = (preferences: ProviderPreference[]) => api.put("/v1/me/provider-preferences", { preferences }).then((r) => r.data);
export const previewPromo = (code: string) => api.post<{ allowed_plans: string[]; campaign_name: string; duration_hours: number }>("/v1/promos/preview", { code }).then((r) => r.data);
export const redeemPromo = (code: string, selected_plan: string) => api.post("/v1/promos/redeem", { code, selected_plan }, { headers: { "Idempotency-Key": crypto.randomUUID() } }).then((r) => r.data);
export const getAdminPromos = () => api.get<{ promos: AdminPromo[] }>("/v1/admin/promos").then((r) => r.data);
export type AdminPromo = { id: string; prefix: string; campaign_name: string; kind: string; allowed_plans: string[]; duration_hours: number; status: string; redemptions: number; max_total_redemptions?: number };
export const createAdminPromo = (payload: Record<string, unknown>) => api.post("/v1/admin/promos", payload).then((r) => r.data);
