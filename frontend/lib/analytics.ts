"use client";

export const ANALYTICS_CONSENT_KEY = "mindmesh.analytics-consent.v1";
let loading: Promise<void> | null = null;
const allowedPaths = new Set(["/", "/contact", "/faq", "/privacy", "/dashboard", "/workspace", "/youtube", "/instagram", "/chat", "/graph", "/stored", "/profile", "/settings"]);

export function hasAnalyticsConsent() {
  return typeof window !== "undefined" && window.localStorage.getItem(ANALYTICS_CONSENT_KEY) === "accepted";
}

export function enableAnalytics(): Promise<void> {
  const id = process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID?.trim();
  if (!id || !/^G-[A-Z0-9]+$/i.test(id)) return Promise.resolve();
  if (window.gtag) return Promise.resolve();
  if (loading) return loading;
  loading = new Promise((resolve) => {
    const script = document.createElement("script");
    script.async = true;
    script.src = `https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(id)}`;
    script.onload = () => {
      window.dataLayer = window.dataLayer || [];
      window.gtag = (...args: unknown[]) => window.dataLayer?.push(args);
      window.gtag("js", new Date());
      window.gtag("config", id, { send_page_view: false });
      resolve();
    };
    script.onerror = () => { loading = null; resolve(); };
    document.head.appendChild(script);
  });
  return loading;
}

export async function trackPageView(path: string) {
  if (!hasAnalyticsConsent()) return;
  const safePath = safeAnalyticsPath(path);
  if (safePath) await sendProductEvent({ event: "page_view", path: safePath });
  const featureForPath: Record<string, "youtube" | "instagram" | "ask_ai" | "stored"> = {
    "/youtube": "youtube", "/instagram": "instagram", "/chat": "ask_ai", "/stored": "stored",
  };
  if (safePath && featureForPath[safePath]) {
    await sendProductEvent({ event: "feature_used", path: safePath, feature: featureForPath[safePath] });
  }
  await enableAnalytics();
  window.gtag?.("event", "page_view", { page_path: safePath || "/" });
}

export async function trackEvent(name: string, params: Record<string, string> = {}) {
  if (!hasAnalyticsConsent()) return;
  await enableAnalytics();
  window.gtag?.("event", name, params);
}

export function trackFeatureUse(feature: "youtube" | "instagram" | "ask_ai" | "stored") {
  if (!hasAnalyticsConsent()) return;
  const path = safeAnalyticsPath(window.location.pathname);
  if (path) void sendProductEvent({ event: "feature_used", feature, path });
}

export function trackHeartbeat() {
  if (!hasAnalyticsConsent() || document.visibilityState !== "visible") return;
  const path = safeAnalyticsPath(window.location.pathname);
  if (path) void sendProductEvent({ event: "heartbeat", path });
}

function safeAnalyticsPath(path: string) {
  const pathname = path.split("?")[0].replace(/\/$/, "") || "/";
  if (allowedPaths.has(pathname)) return pathname;
  if (pathname.startsWith("/source/")) return "/stored";
  return null;
}

function visitorId() {
  const key = "mindmesh.analytics-visitor.v1";
  let id = window.localStorage.getItem(key);
  if (!id || !/^[0-9a-f-]{36}$/i.test(id)) {
    id = window.crypto?.randomUUID?.() || "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => { const r = Math.random() * 16 | 0; return (c === "x" ? r : (r & 3 | 8)).toString(16); });
    window.localStorage.setItem(key, id);
  }
  return id;
}

async function sendProductEvent(event: { event: "page_view" | "heartbeat"; path: string } | { event: "feature_used"; path: string; feature: "youtube" | "instagram" | "ask_ai" | "stored" }) {
  try {
    const host = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/+api\/?$/, "").replace(/\/$/, "");
    await fetch(`${host}/api/v1/analytics/events`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ visitor_id: visitorId(), ...event }), keepalive: true,
    });
  } catch { /* analytics must never block the product experience */ }
}

declare global {
  interface Window {
    dataLayer?: unknown[][];
    gtag?: (...args: unknown[]) => void;
  }
}
