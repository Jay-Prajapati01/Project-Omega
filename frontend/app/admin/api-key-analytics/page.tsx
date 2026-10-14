"use client";

import { useCallback, useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { api } from "@/lib/api";
import { getEntitlement } from "@/lib/commerce";

type Report = {
  mode: string; provider: string; model: string; recording: boolean; message?: string;
  quota_scope_note?: string;
  totals: Record<string, number>;
  by_task_30d?: { task_type: string; attempts: number; successes: number; rate_limits: number }[];
  keys?: { alias: string; provider: string; model: string; attempts_30d: number; successes_30d: number; failures_30d: number; tokens_30d: number; last_used_at: string; auth_failures_30d: number; health: string }[];
  quota_snapshot?: { observed_at: string; model: string; scope: string; source: string; requests_per_day_limit: number | null; requests_per_day_remaining: number | null; requests_per_day_reset: string | null; tokens_per_minute_limit: number | null; tokens_per_minute_remaining: number | null; tokens_per_minute_reset: string | null } | null;
  recent?: Record<string, string | number | boolean | null>[];
};

export default function ApiKeyAnalyticsPage() {
  const [access, setAccess] = useState<"loading" | "allowed" | "denied">("loading");
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    try { setReport((await api.get<Report>("/v1/admin/api-key-analytics")).data); setError(""); }
    catch (e: any) { setError(e?.response?.status === 503 ? "Usage analytics are not available yet. Apply backend/migrations/202610140003_llm_usage_analytics.sql." : "Analytics could not load. Check administrator access and backend connectivity."); }
  }, []);
  useEffect(() => { let alive = true; getEntitlement().then((v) => alive && setAccess(v.role === "owner" || v.role === "admin" ? "allowed" : "denied")).catch(() => alive && setAccess("denied")); return () => { alive = false; }; }, []);
  useEffect(() => { if (access === "allowed") void load(); }, [access, load]);
  if (access === "loading") return <p className="p-8 text-muted">Checking administrator access…</p>;
  if (access === "denied") return <section className="max-w-xl rounded-2xl border-2 border-ink bg-card p-6"><h1 className="text-2xl font-extrabold">Admin access required</h1><p className="mt-2 text-muted">This page is limited to verified workspace owners and administrators.</p></section>;
  const totals = report?.totals || {};
  const cards = [["Attempts · 24h", "attempts_24h"], ["Successful · 24h", "successes_24h"], ["Failed · 24h", "failures_24h"], ["Tokens · 24h", "total_tokens_24h"], ["Rate limits · 24h", "rate_limits_24h"], ["Avg latency", "average_latency_ms_24h"], ["Retries · 24h", "retries_24h"], ["Fallbacks · 24h", "fallbacks_24h"]] as const;
  return <main className="mx-auto max-w-7xl space-y-6">
    <header className="flex flex-wrap items-end justify-between gap-4"><div><p className="font-mono text-xs font-bold uppercase tracking-widest text-brand">MindMesh / administration</p><h1 className="mt-2 text-3xl font-extrabold">API Key Analytics</h1><p className="mt-2 text-sm text-muted">Provider attempts and quota telemetry. Prompts and completions are never shown.</p></div><button onClick={() => void load()} className="brut-btn flex items-center gap-2 rounded-lg bg-card px-3 py-2"><RefreshCw size={16}/> Refresh</button></header>
    {error && <div role="alert" className="rounded-xl border border-amber-500/50 bg-amber-500/10 p-4 text-sm">{error}</div>}
    {report && <section className="rounded-2xl border-2 border-ink bg-card p-5"><h2 className="text-lg font-extrabold">{report.mode === "local" ? "Local development" : "Active provider"}</h2><p className="mt-1 text-sm text-muted">{report.provider} · {report.model}</p>{report.message && <p className="mt-4 rounded-xl bg-surface p-4 text-sm">{report.message}</p>}</section>}
    {report?.recording && <>
      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{cards.map(([label,key]) => <article key={key} className="rounded-2xl border-2 border-ink bg-card p-4"><p className="text-xs text-muted">{label}</p><p className="mt-2 text-2xl font-black">{totals[key]?.toLocaleString() ?? "—"}</p></article>)}</section>
      <section className="rounded-2xl border-2 border-ink bg-card p-5"><h2 className="text-lg font-extrabold">Usage by task · 30 days</h2><p className="mt-1 text-xs text-muted">{report.quota_scope_note}</p><div className="mt-4 overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr className="bg-surface"><th className="p-3">Task</th><th className="p-3">Attempts</th><th className="p-3">Successes</th><th className="p-3">429s</th></tr></thead><tbody>{report.by_task_30d?.map((r) => <tr key={r.task_type} className="border-t border-ink/10"><td className="p-3">{r.task_type}</td><td className="p-3">{r.attempts}</td><td className="p-3">{r.successes}</td><td className="p-3">{r.rate_limits}</td></tr>)}</tbody></table></div></section>
      <section className="rounded-2xl border-2 border-ink bg-card p-5"><h2 className="text-lg font-extrabold">Credential alias activity · 30 days</h2><p className="mt-1 text-xs text-muted">Attributed usage only; this is not a per-key quota. Raw credentials are never shown.</p><div className="mt-4 overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr className="bg-surface"><th className="p-3">Alias</th><th className="p-3">Provider / model</th><th className="p-3">Attempts</th><th className="p-3">Success / fail</th><th className="p-3">Tokens</th><th className="p-3">Last used</th><th className="p-3">Health</th></tr></thead><tbody>{report.keys?.map((k) => <tr key={k.alias} className="border-t border-ink/10"><td className="p-3">{k.alias}</td><td className="p-3">{k.provider} · {k.model}</td><td className="p-3">{k.attempts_30d.toLocaleString()}</td><td className="p-3">{k.successes_30d.toLocaleString()} / {k.failures_30d.toLocaleString()}</td><td className="p-3">{k.tokens_30d.toLocaleString()}</td><td className="p-3">{new Date(k.last_used_at).toLocaleString()}</td><td className="p-3">{k.health}{k.auth_failures_30d ? ` (${k.auth_failures_30d} auth errors)` : ""}</td></tr>)}{!report.keys?.length && <tr><td colSpan={7} className="p-4 text-center text-muted">No external provider attempts recorded yet.</td></tr>}</tbody></table></div></section>
      {report.quota_snapshot && <section className="rounded-2xl border-2 border-ink bg-card p-5"><h2 className="text-lg font-extrabold">Latest provider quota headers</h2><p className="mt-1 text-xs text-muted">Scope: {report.quota_snapshot.scope} · observed {new Date(report.quota_snapshot.observed_at).toLocaleString()} · source: {report.quota_snapshot.source}</p><div className="mt-4 grid gap-3 sm:grid-cols-2"><p className="rounded-xl bg-surface p-3 text-sm">Requests/day: {report.quota_snapshot.requests_per_day_remaining ?? "unknown"} remaining of {report.quota_snapshot.requests_per_day_limit ?? "unknown"} · reset {report.quota_snapshot.requests_per_day_reset ?? "unknown"}</p><p className="rounded-xl bg-surface p-3 text-sm">Tokens/minute: {report.quota_snapshot.tokens_per_minute_remaining ?? "unknown"} remaining of {report.quota_snapshot.tokens_per_minute_limit ?? "unknown"} · reset {report.quota_snapshot.tokens_per_minute_reset ?? "unknown"}</p></div></section>}
      <section className="overflow-hidden rounded-2xl border-2 border-ink bg-card"><div className="p-5"><h2 className="text-lg font-extrabold">Recent provider attempts</h2><p className="mt-1 text-xs text-muted">Last 100 calls · aliases only, never API keys</p></div><div className="overflow-x-auto"><table className="w-full text-left text-xs"><thead className="bg-surface"><tr>{["Time","Task","Model","Key alias","Status","HTTP","Latency","Tokens","Quota scope","Error"].map((v) => <th className="whitespace-nowrap p-3" key={v}>{v}</th>)}</tr></thead><tbody>{report.recent?.map((r,i) => <tr className="border-t border-ink/10" key={`${r.request_id}-${i}`}><td className="whitespace-nowrap p-3">{String(r.created_at).slice(0,19).replace("T"," ")}</td><td className="p-3">{r.task_type}</td><td className="p-3">{r.model}</td><td className="p-3">{r.key_alias}</td><td className="p-3">{r.status}</td><td className="p-3">{r.http_status ?? "—"}</td><td className="p-3">{r.latency_ms ?? "—"} ms</td><td className="p-3">{r.total_tokens ?? "unknown"}</td><td className="p-3">{r.quota_scope}</td><td className="p-3">{r.error_code ?? "—"}</td></tr>)}</tbody></table></div></section>
    </>}
  </main>;
}
