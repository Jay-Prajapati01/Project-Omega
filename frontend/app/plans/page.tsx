"use client";

import Link from "next/link";

const cards = [
  {
    href: "/plans/ai-providers",
    title: "AI providers",
    text: "Bring your own key",
  },
  {
    href: "/plans/usage",
    title: "Plan usage",
    text: "Limits and remaining actions",
  },
  {
    href: "/plans/billing",
    title: "Billing & plans",
    text: "Plans and promo access",
  },
];

export default function PlansPage() {
  return (
    <div className="mx-auto max-w-4xl">
      <p className="font-mono text-xs font-bold uppercase tracking-widest text-brand">
        Workspace / Plans &amp; pricing
      </p>
      <h1 className="mt-2 text-4xl font-extrabold">Plans &amp; pricing</h1>
      <p className="mt-3 max-w-2xl text-muted">
        Your account&apos;s plan state — providers, usage and billing. This is
        separate from the public pricing page.
      </p>
      <div className="mt-8 grid gap-3 sm:grid-cols-3">
        {cards.map((card) => (
          <Link
            key={card.href}
            href={card.href}
            className="rounded-xl border-2 border-ink bg-card p-4 font-bold shadow-card hover:bg-paper-card"
          >
            {card.title}
            <br />
            <span className="text-sm font-normal text-muted">{card.text}</span>
          </Link>
        ))}
      </div>
    </div>
  );
}
