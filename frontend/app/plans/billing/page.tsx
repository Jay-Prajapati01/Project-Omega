"use client";

import { type FormEvent, useEffect, useState } from "react";
import { BadgeCheck, KeyRound, TicketPercent } from "lucide-react";
import {
  getEntitlement,
  getPlans,
  previewPromo,
  redeemPromo,
  type Entitlement,
  type Plan,
} from "@/lib/commerce";

type PromoPreview = {
  allowed_plans: string[];
  campaign_name: string;
  duration_hours: number;
};

export default function BillingPage() {
  const [entitlement, setEntitlement] = useState<Entitlement | null>(null);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [code, setCode] = useState("");
  const [preview, setPreview] = useState<PromoPreview | null>(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    getEntitlement()
      .then((data) => {
        setEntitlement(data);
        return getPlans();
      })
      .then((data) => setPlans(data.plans))
      .catch(() => setError("Billing is unavailable right now."));
  }, []);

  async function apply(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    try {
      setPreview(await previewPromo(code));
    } catch (err: any) {
      setPreview(null);
      setMessage(
        err?.response?.data?.detail?.message ||
          "That promo code could not be applied."
      );
    } finally {
      setBusy(false);
    }
  }

  async function redeem(plan: string) {
    setBusy(true);
    try {
      const result: any = await redeemPromo(code, plan);
      setMessage(
        `Promo applied. Your effective plan is ${result.effective_plan}.`
      );
      setPreview(null);
      setEntitlement(await getEntitlement());
    } catch (err: any) {
      setMessage(
        err?.response?.data?.detail?.message || "Promo redemption failed."
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-4xl">
      <p className="font-mono text-xs font-bold uppercase tracking-widest text-brand">
        Plans &amp; pricing / Billing &amp; plans
      </p>
      <h1 className="mt-2 text-4xl font-extrabold">Billing &amp; plans</h1>
      <p className="mt-3 max-w-2xl text-muted">
        Your account&apos;s current plan and promo access — this is your
        billing state, not the public pricing page.
      </p>
      {error && <p className="mt-5 font-semibold">{error}</p>}

      {entitlement && (
        <section className="mt-8 rounded-3xl border-2 border-ink bg-card p-6 shadow-card">
          <div className="flex items-center gap-3">
            <BadgeCheck className="h-5 w-5 text-brand" />
            <h2 className="text-xl font-extrabold">Current plan</h2>
          </div>
          <p className="mt-3 text-2xl font-black capitalize">
            {entitlement.effective_plan}
          </p>
          <p className="mt-1 text-sm text-muted">
            Base plan: {entitlement.base_plan} · Usage period:{" "}
            {entitlement.period} ·{" "}
            {entitlement.ai_mode === "byok"
              ? "Your AI key active"
              : "MindMesh managed AI"}
            {entitlement.beta_tester ? " · Beta tester" : ""}
          </p>
          {entitlement.grants.length > 0 && (
            <div className="mt-4">
              <h3 className="text-sm font-bold uppercase tracking-wider text-muted">
                Active promo grants
              </h3>
              <ul className="mt-2 space-y-2">
                {entitlement.grants.map((grant) => (
                  <li
                    key={grant.id}
                    className="rounded-xl border-2 border-ink bg-surface p-3 text-sm"
                  >
                    <b className="capitalize">{grant.plan}</b>
                    {grant.cohort ? ` · ${grant.cohort}` : ""} · expires{" "}
                    {grant.expires_at}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
      )}

      <section className="mt-6 rounded-3xl border-2 border-ink bg-card p-6 shadow-card">
        <div className="flex items-start gap-3">
          <TicketPercent className="mt-1 h-5 w-5 shrink-0 text-brand" />
          <div>
            <h2 className="text-xl font-extrabold">Have a promo code?</h2>
            <p className="text-sm text-muted">
              Promos add temporary plan access. They never grant account
              administration.
            </p>
          </div>
        </div>
        <form onSubmit={apply} className="mt-5 flex flex-col gap-3 sm:flex-row">
          <input
            aria-label="Promo code"
            value={code}
            onChange={(event) => setCode(event.target.value)}
            placeholder="Enter promo code"
            className="min-w-0 w-full flex-1 rounded-xl border-2 border-ink bg-surface px-4 py-3 font-mono uppercase"
          />
          <button
            disabled={busy}
            className="brut-btn w-full rounded-xl bg-orange px-5 py-3 font-bold disabled:opacity-50 sm:w-auto"
          >
            {busy ? "Checking…" : "Apply"}
          </button>
        </form>
        {preview && (
          <div className="mt-5 rounded-xl border-2 border-ink bg-surface p-4">
            <p className="font-bold">
              {preview.campaign_name} gives {preview.duration_hours} hours of
              access. Choose your plan:
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              {preview.allowed_plans.map((plan) => (
                <button
                  key={plan}
                  disabled={busy}
                  onClick={() => redeem(plan)}
                  className="brut-btn rounded-lg bg-card px-4 py-2 font-bold capitalize"
                >
                  Use {plan}
                </button>
              ))}
            </div>
          </div>
        )}
        {message && (
          <p role="status" className="mt-4 text-sm font-semibold">
            {message}
          </p>
        )}
      </section>

      {plans.length > 0 && (
        <section className="mt-6 rounded-3xl border-2 border-ink bg-card p-6 shadow-card">
          <div className="flex items-center gap-3">
            <KeyRound className="h-5 w-5 text-brand" />
            <h2 className="text-xl font-extrabold">Available plans</h2>
          </div>
          <ul className="mt-4 space-y-2">
            {plans.map((plan) => (
              <li
                key={plan.key}
                className="flex items-center justify-between gap-3 rounded-xl border-2 border-ink bg-surface p-3 text-sm"
              >
                <span>
                  <b className="capitalize">{plan.name}</b>{" "}
                  <span className="text-muted">
                    {plan.price_paise
                      ? `₹${plan.price_paise / 100} / month`
                      : "₹0 / month"}
                  </span>
                </span>
                {entitlement?.effective_plan === plan.key && (
                  <span className="rounded-full bg-orange px-3 py-1 text-xs font-bold">
                    Current
                  </span>
                )}
              </li>
            ))}
          </ul>
          <p className="mt-3 text-sm text-muted">
            Online checkout is introduced only after payment verification is
            configured.
          </p>
        </section>
      )}
    </div>
  );
}
