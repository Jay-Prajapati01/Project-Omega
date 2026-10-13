"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Activity, Eye, RefreshCw, Users, Youtube, Instagram, MessageSquare, Library, TicketPercent } from "lucide-react";
import { getEntitlement } from "@/lib/commerce";
import { api } from "@/lib/api";

type Summary = {
  generated_at: string;
  totals: { all_time_visitors: number; visitors_24h: number; visitors_7d: number; online_now: number; page_views: number; visitors_30d: number };
  daily: { date: string; visitors: number }[];
  pages: { path: string; views: number; visitors: number }[];
  features: { feature: string; uses: number; users: number }[];
  window: string;
};

const featureIcon: Record<string, typeof Youtube> = { youtube: Youtube, instagram: Instagram, ask_ai: MessageSquare, stored: Library };
const featureName: Record<string, string> = { youtube: "YouTube", instagram: "Instagram", ask_ai: "Ask AI", stored: "Stored" };

export default function AdminPortalPage() {
  const [access, setAccess] = useState<"loading" | "allowed" | "denied">("loading");
  const [summary, setSummary] = useState<Summary | null>(null);
  const [error, setError] = useState("");
  const [updated, setUpdated] = useState("");
  const load = useCallback(async () => {
    try {
      const { data } = await api.get<Summary>("/v1/admin/analytics");
      setSummary(data);
      setUpdated(new Date(data.generated_at).toLocaleTimeString());
      setError("");
    } catch (e: any) {
      setError(e?.response?.status === 503
        ? "Analytics storage needs setup. Apply backend/migrations/202610140001_analytics.sql to the connected database."
        : "Analytics could not load. Confirm admin permissions and backend connectivity.");
    }
  }, []);

  useEffect(() => {
    let active = true;
    getEntitlement().then((value) => {
      if (!active) return;
      if (value.role === "owner" || value.role === "admin") setAccess("allowed");
      else setAccess("denied");
    }).catch(() => { if (active) setAccess("denied"); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (access !== "allowed") return;
    void load();
    const timer = window.setInterval(() => {
      if (document.visibilityState === "visible") void load();
    }, 5000);
    return () => window.clearInterval(timer);
  }, [access, load]);

  if (access === "loading") return <p className="p-8 text-muted">Checking administrator access…</p>;
  if (access === "denied") return <div className="max-w-xl rounded-2xl border-2 border-ink bg-card p-6"><h1 className="text-2xl font-extrabold">Admin access required</h1><p className="mt-2 text-muted">This portal is limited to verified workspace owners and administrators.</p></div>;

  const totals = summary?.totals;
  const maxDaily = Math.max(1, ...(summary?.daily.map((item) => item.visitors) || []));
  const cards = [
    { label: "Visitors · all time", value: totals?.all_time_visitors, icon: Users },
    { label: "Visitors · last 24 hours", value: totals?.visitors_24h, icon: Activity },
    { label: "Online · last 5 minutes", value: totals?.online_now, icon: Users, live: true },
    { label: "Page views · 30 days", value: totals?.page_views, icon: Eye },
  ];

  return <div className="mx-auto max-w-7xl">
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div><p className="font-mono text-xs font-bold uppercase tracking-widest text-brand">MindMesh / administration</p><h1 className="mt-2 text-3xl font-extrabold sm:text-4xl">Usage analytics</h1><p className="mt-3 max-w-2xl text-muted">Anonymous visitor, page, and feature totals. Dashboard refreshes every five seconds; no names or content are shown.</p></div>
      <div className="flex items-center gap-3"><span className="flex items-center gap-2 text-xs font-semibold text-muted"><span className="h-2 w-2 animate-pulse rounded-full bg-emerald-500" />Live · {updated || "connecting"}</span><button onClick={() => void load()} aria-label="Refresh analytics" className="brut-btn rounded-lg bg-card p-2"><RefreshCw size={17} /></button></div>
    </div>

    {error && <div role="alert" className="mt-6 rounded-2xl border-2 border-amber-500/40 bg-amber-500/10 p-4 text-sm">{error}</div>}
    <div className="mt-7 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{cards.map(({ label, value, icon: Icon, live }) => <article key={label} className="rounded-2xl border-2 border-ink bg-card p-5 shadow-card"><div className="flex items-center justify-between"><span className="text-sm text-muted">{label}</span><Icon className="h-5 w-5 text-brand" />{live && <span className="sr-only">Updates live</span>}</div><p className="mt-3 text-3xl font-black">{value?.toLocaleString() ?? "—"}</p></article>)}</div>

    <div className="mt-5 grid gap-5 xl:grid-cols-[1.25fr_1fr]">
      <section className="rounded-2xl border-2 border-ink bg-card p-5 shadow-card"><div className="flex items-baseline justify-between gap-3"><div><h2 className="text-xl font-extrabold">Daily visitors</h2><p className="mt-1 text-sm text-muted">Unique anonymous browsers per UTC day · last 14 days</p></div><span className="text-sm font-semibold">7 days: {totals?.visitors_7d?.toLocaleString() ?? "—"}</span></div>
        <div className="mt-6 flex h-48 items-end gap-2 border-b border-ink/15 px-1">{summary?.daily.map((item) => <div key={item.date} title={`${item.date}: ${item.visitors} visitors`} className="group flex h-full min-w-0 flex-1 flex-col justify-end"><div className="mb-1 text-center text-[10px] text-muted opacity-0 group-hover:opacity-100">{item.visitors}</div><div className="min-h-1 rounded-t-md bg-brand/80 transition-colors group-hover:bg-brand" style={{ height: `${Math.max(2, item.visitors / maxDaily * 78)}%` }} /><span className="mt-2 truncate text-center text-[9px] text-muted">{item.date.slice(5)}</span></div>)}</div>
      </section>
      <section className="rounded-2xl border-2 border-ink bg-card p-5 shadow-card"><h2 className="text-xl font-extrabold">Feature usage</h2><p className="mt-1 text-sm text-muted">Feature page visits and completed actions · last 30 days</p><div className="mt-4 space-y-3">{["youtube", "instagram", "ask_ai", "stored"].map((key) => { const row = summary?.features.find((item) => item.feature === key); const Icon = featureIcon[key]; return <div key={key} className="flex items-center gap-3 rounded-xl border border-ink/10 bg-surface p-3"><Icon className="h-5 w-5 text-brand" /><span className="flex-1 font-bold">{featureName[key]}</span><span className="text-right text-sm"><b>{row?.uses ?? 0}</b><span className="ml-1 text-muted">uses</span><span className="ml-3 text-muted">{row?.users ?? 0} visitors</span></span></div>; })}</div></section>
    </div>

    <div className="mt-5 grid gap-5 xl:grid-cols-2">
      <section className="overflow-hidden rounded-2xl border-2 border-ink bg-card shadow-card"><div className="border-b border-ink/10 p-5"><h2 className="text-xl font-extrabold">Pages explored</h2><p className="mt-1 text-sm text-muted">Views and unique anonymous visitors · last 30 days</p></div><div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead className="bg-surface text-muted"><tr><th className="px-5 py-3">Page</th><th className="px-5 py-3">Views</th><th className="px-5 py-3">Visitors</th></tr></thead><tbody>{summary?.pages.map((page) => <tr key={page.path} className="border-t border-ink/10"><td className="px-5 py-3 font-mono">{page.path}</td><td className="px-5 py-3">{page.views.toLocaleString()}</td><td className="px-5 py-3">{page.visitors.toLocaleString()}</td></tr>)}{!summary?.pages.length && <tr><td colSpan={3} className="px-5 py-8 text-center text-muted">No consented analytics yet.</td></tr>}</tbody></table></div></section>
      <div className="space-y-5"><section className="rounded-2xl border-2 border-ink bg-card p-5 shadow-card"><h2 className="text-xl font-extrabold">Privacy and counting</h2><ul className="mt-3 list-disc space-y-2 pl-5 text-sm text-muted"><li>Visitors are random browser IDs, not names or account IDs.</li><li>Online means a browser sent an event in the last five minutes.</li><li>Analytics starts only after the visitor accepts the consent prompt.</li><li>Page paths are allowlisted; query strings and source IDs are discarded.</li></ul></section><Link href="/admin/promo-codes" className="flex items-center gap-3 rounded-2xl border-2 border-ink bg-card p-5 shadow-card transition hover:bg-surface"><TicketPercent className="h-5 w-5 text-brand" /><span className="flex-1"><b>Promo campaigns</b><span className="block text-sm text-muted">Manage temporary plan grants</span></span><span aria-hidden>→</span></Link></div>
    </div>
  </div>;
}
