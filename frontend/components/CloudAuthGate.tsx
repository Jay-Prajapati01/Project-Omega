"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import Link from "next/link";
import { useQueryClient } from "@tanstack/react-query";
import type { Session } from "@supabase/supabase-js";
import { getSupabase } from "@/lib/supabaseClient";
import { useAppStore } from "@/lib/store";
import { processManager } from "@/lib/processManager";
import { NotificationBridge } from "./NotificationBridge";

const PUBLIC_ROUTES = ["/", "/contact", "/pricing", "/login", "/signup", "/forgot-password", "/reset-password"];
const AuthContext = createContext<{ session: Session | null; ready: boolean; error: string }>({ session: null, ready: false, error: "" });
export const useAuth = () => useContext(AuthContext);

export function CloudAuthGate({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const cache = useQueryClient();
  const [session, setSession] = useState<Session | null>(null);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState("");
  const isPublic = PUBLIC_ROUTES.includes(pathname);

  const meta = (session?.user.user_metadata ?? {}) as Record<string, unknown>;
  const rawName =
    (typeof meta.preferred_name === "string" && meta.preferred_name.trim()) ||
    (typeof meta.full_name === "string" && meta.full_name.trim()) ||
    session?.user.email?.split("@")[0] ||
    "Your profile";
  const displayName = rawName.trim();
  const initials =
    displayName.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join("").toUpperCase() || "M";

  useEffect(() => {
    try {
      const { data } = getSupabase().auth.onAuthStateChange((_event, nextSession) => {
        const owner = nextSession?.user.id || "";
        const previous = localStorage.getItem("mindmesh-session-owner") || "";
        if (!owner || previous !== owner) {
          void cache.cancelQueries();
          cache.clear();
          processManager.resetForAccountChange();
          useAppStore.setState(useAppStore.getInitialState(), true);
          for (const storage of [localStorage, sessionStorage]) {
            for (const key of Object.keys(storage)) {
              if (key.startsWith("mindmesh")) storage.removeItem(key);
            }
          }
        }
        if (owner) localStorage.setItem("mindmesh-session-owner", owner);
        setSession(nextSession);
        setReady(true);
      });
      return () => data.subscription.unsubscribe();
    } catch {
      setError("Sign-in is currently unavailable. Please try again later.");
      setReady(true);
    }
  }, [cache]);

  useEffect(() => {
    if (ready && !session && !isPublic && !error) {
      router.replace(`/login?next=${encodeURIComponent(pathname + window.location.search)}`);
    }
  }, [ready, session, isPublic, pathname, router, error]);

  return <AuthContext.Provider value={{ session, ready, error }}>
    {isPublic ? children : !ready || !session ? (
      <main className="grid min-h-screen place-items-center p-8" role="status">{error || "Opening your workspace…"}</main>
    ) : (
      <div key={session.user.id}>
        <NotificationBridge />
        <div className="flex items-center justify-end gap-3 border-b border-ink/10 bg-card px-4 py-2 text-sm">
          <Link
            href="/profile"
            title="Open your profile"
            className="flex max-w-[min(100%,22rem)] items-center gap-3 rounded-2xl border-2 border-ink bg-surface px-2.5 py-1.5 transition-colors hover:bg-paper-card"
          >
            <span className="grid h-8 w-8 shrink-0 place-items-center rounded-xl border-2 border-ink bg-orange text-[11px] font-extrabold text-ink">
              {initials}
            </span>
            <span className="min-w-0 text-left leading-tight">
              <span className="block truncate text-sm font-extrabold text-foreground">{displayName}</span>
              <span className="block truncate text-xs text-muted">{session.user.email}</span>
            </span>
          </Link>
          <button className="font-bold underline" onClick={async () => {
            const { error: signOutError } = await getSupabase().auth.signOut();
            if (signOutError) setError("Unable to sign out. Please try again.");
            else router.replace("/login");
          }}>Sign out</button>
          {error && <span role="alert">{error}</span>}
        </div>
        {children}
      </div>
    )}
  </AuthContext.Provider>;
}
