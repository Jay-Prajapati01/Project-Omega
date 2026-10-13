"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { ANALYTICS_CONSENT_KEY, enableAnalytics, trackHeartbeat, trackPageView } from "@/lib/analytics";

export function CookieConsent() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [choice, setChoice] = useState<string | null>(null);
  const gaConfigured = Boolean(process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID?.trim());

  useEffect(() => {
    const saved = localStorage.getItem(ANALYTICS_CONSENT_KEY);
    setChoice(saved);
    setOpen(!saved);
    const show = () => setOpen(true);
    window.addEventListener("mindmesh:open-cookie-settings", show);
    return () => window.removeEventListener("mindmesh:open-cookie-settings", show);
  }, [gaConfigured]);

  useEffect(() => { if (choice === "accepted") void trackPageView(`${pathname}${window.location.search}`); }, [choice, pathname]);

  useEffect(() => {
    if (choice !== "accepted") return;
    let lastSent = 0;
    const onActivity = () => {
      const now = Date.now();
      if (now - lastSent < 60_000) return;
      lastSent = now;
      trackHeartbeat();
    };
    window.addEventListener("pointerdown", onActivity, { passive: true });
    window.addEventListener("keydown", onActivity);
    window.addEventListener("touchstart", onActivity, { passive: true });
    return () => {
      window.removeEventListener("pointerdown", onActivity);
      window.removeEventListener("keydown", onActivity);
      window.removeEventListener("touchstart", onActivity);
    };
  }, [choice]);

  function choose(value: "accepted" | "rejected") {
    localStorage.setItem(ANALYTICS_CONSENT_KEY, value);
    setChoice(value);
    setOpen(false);
    if (value === "accepted" && gaConfigured) void enableAnalytics();
  }

  if (!open) return null;
  return (
    <aside role="dialog" aria-label="Analytics cookie preferences" aria-modal="false" className="fixed inset-x-3 bottom-3 z-[100] mx-auto max-w-3xl rounded-2xl border-2 border-ink bg-paper p-5 text-ink shadow-[5px_5px_0_var(--ink)] sm:inset-x-6 sm:bottom-6">
      <p className="font-display text-xl uppercase">Help improve MindMesh</p>
      <p className="mt-2 text-sm text-ink-muted">Would you like to share anonymous usage insights with us? This helps us understand which pages and features are useful. Analytics is optional and stays off unless you choose to allow it. You can change your choice anytime in Cookie settings.{gaConfigured ? " Google Analytics will also run only if you allow analytics." : ""}</p>
      <div className="mt-4 flex flex-wrap items-center gap-3 text-sm font-bold">
        <button onClick={() => choose("accepted")} className="brut-btn rounded-xl bg-orange px-4 py-2">Allow analytics</button>
        <button onClick={() => choose("rejected")} className="brut-btn rounded-xl bg-paper-alt px-4 py-2">Keep analytics off</button>
        <Link href="/privacy" className="underline underline-offset-4">Privacy notice</Link>
      </div>
    </aside>
  );
}
