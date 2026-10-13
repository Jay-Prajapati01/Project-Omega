"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { createAdminPromo, getAdminPromos, type AdminPromo } from "@/lib/commerce";

export default function PromoAdminPage() {
  const [promos, setPromos] = useState<AdminPromo[]>([]);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [name, setName] = useState("");
  const [hours, setHours] = useState("720");
  const [limit, setLimit] = useState("100");

  const refresh = useCallback(async () => {
    try {
      const data = await getAdminPromos();
      setPromos(data.promos);
    } catch (error: any) {
      setMessage(error?.response?.status === 403 ? "Your account does not have admin access." : "Promo manager is unavailable.");
    }
  }, []);

  // Effects may return only a cleanup function, never a Promise.
  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    try {
      const result = await createAdminPromo({
        campaign_name: name,
        kind: "beta_grant",
        allowed_plans: ["pro"],
        duration_hours: Number(hours),
        max_total_redemptions: Number(limit),
      });
      setMessage(`Promo created. Copy it now: ${result.code}`);
      setName("");
      void refresh();
    } catch (error: any) {
      setMessage(error?.response?.data?.detail?.message || "Could not create promo.");
    } finally {
      setBusy(false);
    }
  }

  return <div className="mx-auto max-w-5xl">
    <p className="font-mono text-xs font-bold uppercase tracking-widest text-brand">Admin / campaigns</p>
    <h1 className="mt-2 text-3xl font-extrabold sm:text-4xl">Promo code manager</h1>
    <p className="mt-3 text-muted">Promo codes grant temporary plan access only. They never create owner or admin access.</p>
    <form onSubmit={submit} className="mt-7 grid gap-4 rounded-3xl border-2 border-ink bg-card p-4 shadow-card sm:grid-cols-3 sm:p-6">
      <label className="text-sm font-bold">Campaign name<input required value={name} onChange={(event) => setName(event.target.value)} className="mt-2 w-full rounded-xl border-2 border-ink bg-surface px-3 py-2" /></label>
      <label className="text-sm font-bold">Access hours<input required type="number" min="1" max="8760" value={hours} onChange={(event) => setHours(event.target.value)} className="mt-2 w-full rounded-xl border-2 border-ink bg-surface px-3 py-2" /></label>
      <label className="text-sm font-bold">Redemption cap<input required type="number" min="1" value={limit} onChange={(event) => setLimit(event.target.value)} className="mt-2 w-full rounded-xl border-2 border-ink bg-surface px-3 py-2" /></label>
      <button disabled={busy} className="brut-btn rounded-xl bg-orange px-5 py-3 font-bold sm:col-span-3">{busy ? "Creating…" : "Create beta Pro promo"}</button>
    </form>
    {message && <p role="status" className="mt-4 font-bold">{message}</p>}
    <div className="mt-7 overflow-x-auto rounded-3xl border-2 border-ink bg-card shadow-card"><div className="min-w-[520px]">
      <div className="grid grid-cols-4 gap-3 border-b-2 border-ink p-4 text-xs font-bold uppercase tracking-wider"><span>Campaign</span><span>Plan</span><span>Usage</span><span>Status</span></div>
      {promos.map((promo) => <div key={promo.id} className="grid grid-cols-4 gap-3 border-b border-ink/15 p-4 text-sm"><span><b>{promo.campaign_name}</b><br /><code>{promo.prefix}</code></span><span className="capitalize">{promo.allowed_plans.join(", ")}<br />{promo.duration_hours} hours</span><span>{promo.redemptions} / {promo.max_total_redemptions || "∞"}</span><span className="capitalize">{promo.status}</span></div>)}
      {!promos.length && <p className="p-5 text-muted">No promo campaigns are visible yet.</p>}
    </div></div>
  </div>;
}
