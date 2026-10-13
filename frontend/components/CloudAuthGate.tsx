"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
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
        {children}
      </div>
    )}
  </AuthContext.Provider>;
}
