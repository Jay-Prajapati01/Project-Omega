"use client";

import { useState, useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import Link from "next/link";
import { Menu, UserRound, X } from "lucide-react";
import { Nav } from "./Nav";
import { ActiveProcessesBanner } from "./ActiveProcessesBanner";
import { ThemeToggle } from "./ThemeToggle";
import { CommandPalette } from "./dashboard/CommandPalette";
import { useAppStore } from "@/lib/store";
import { applyThemeToDOM, applyAccentToDOM, applyDensityToDOM } from "./ThemeEffect";
import { useAuth } from "./CloudAuthGate";
import { getSupabase } from "@/lib/supabaseClient";

const CHROMELESS_ROUTES = ["/", "/contact", "/pricing", "/login", "/signup", "/forgot-password", "/reset-password"];
const NAV_COLLAPSED_KEY = "mindmesh-nav-collapsed";

export function Shell({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const settings = useAppStore((s) => s.settings);
  const pathname = usePathname();
  const router = useRouter();
  const { session } = useAuth();
  const [signOutError, setSignOutError] = useState("");
  const metadata = (session?.user.user_metadata ?? {}) as Record<string, unknown>;
  const accountName =
    (typeof metadata.preferred_name === "string" && metadata.preferred_name.trim()) ||
    (typeof metadata.full_name === "string" && metadata.full_name.trim()) ||
    session?.user.email?.split("@")[0] || "Your profile";
  const initials = accountName.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join("").toUpperCase() || "M";

  async function signOut() {
    const { error } = await getSupabase().auth.signOut();
    if (error) setSignOutError("Unable to sign out. Please try again.");
    else router.replace("/login");
  }

  // Apply theme on mount (fixes hydration mismatch issue)
  useEffect(() => {
    applyThemeToDOM(settings.theme);
    applyAccentToDOM(settings.accentColor);
    applyDensityToDOM(settings.density);
  }, [settings.theme, settings.accentColor, settings.density]);

  // Restore the persisted sidebar state after mount (localStorage is
  // unavailable during SSR, so the first paint is always expanded).
  useEffect(() => {
    try {
      setCollapsed(localStorage.getItem(NAV_COLLAPSED_KEY) === "1");
    } catch {
      // storage unavailable — sidebar just starts expanded
    }
  }, []);

  const toggleCollapsed = () =>
    setCollapsed((v) => {
      const next = !v;
      try {
        localStorage.setItem(NAV_COLLAPSED_KEY, next ? "1" : "0");
      } catch {
        // storage unavailable — state still toggles for this visit
      }
      return next;
    });

  // Landing + contact pages render without the app sidebar/chrome
  if (CHROMELESS_ROUTES.includes(pathname)) {
    return <div className="min-h-screen">{children}</div>;
  }

  return (
    <div className="paper-grain flex min-h-screen bg-background text-foreground transition-colors duration-200">
      {/* Desktop sidebar (collapsible, preference persisted) */}
      <div className="sticky top-0 hidden h-screen self-start md:block">
        <Nav collapsed={collapsed} onToggleCollapse={toggleCollapsed} />
      </div>

      {/* Mobile drawer */}
      {open && (
        <div className="fixed inset-0 z-40 md:hidden">
          <div
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={() => setOpen(false)}
          />
          <div className="absolute left-0 top-0 h-full w-[min(18rem,calc(100vw-2rem))] border-r-2 border-ink bg-card shadow-brut-lg">
            <Nav onNavigate={() => setOpen(false)} />
          </div>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        {/* Account controls share the top row with the sidebar, avoiding a blank strip above navigation. */}
        <header className="hidden h-14 items-center justify-end gap-3 bg-transparent px-5 md:flex">
          <Link
            href="/profile"
            title="Open your profile"
            className="flex max-w-[min(100%,22rem)] items-center gap-3 rounded-xl border-2 border-ink bg-surface px-2.5 py-1 transition-colors hover:bg-paper-card"
          >
            <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg border-2 border-ink bg-orange text-[11px] font-extrabold text-ink">{initials}</span>
            <span className="min-w-0 text-left leading-tight">
              <span className="block truncate text-sm font-extrabold text-foreground">{accountName}</span>
              <span className="block truncate text-xs text-muted">{session?.user.email}</span>
            </span>
          </Link>
          <button className="rounded-lg px-2 py-2 text-sm font-bold underline underline-offset-4 hover:bg-surface" onClick={() => void signOut()}>Sign out</button>
          {signOutError && <span role="alert" className="text-xs text-red-700">{signOutError}</span>}
        </header>

        {/* Mobile top bar */}
        <header className="flex items-center gap-3 border-b-2 border-ink bg-card px-4 py-3 md:hidden">
          <button onClick={() => setOpen((v) => !v)} aria-label="Toggle menu" className="text-foreground">
            {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
          <Link
            href="/"
            className="text-lg font-extrabold tracking-tight text-foreground"
          >
            MindMesh
          </Link>
          <div className="ml-auto">
            <ThemeToggle className="-mr-2 rounded-lg p-1.5 text-foreground-3 transition-colors hover:bg-surface hover:text-foreground" />
          </div>
          <Link href="/profile" aria-label="Open your profile" className="grid h-8 w-8 shrink-0 place-items-center rounded-lg border-2 border-ink bg-orange text-xs font-extrabold text-ink">{initials || <UserRound className="h-4 w-4" />}</Link>
          <button onClick={() => void signOut()} className="text-xs font-bold underline underline-offset-4">Sign out</button>
        </header>

        <main className="flex-1 p-3 sm:p-6 lg:p-8">{children}</main>
      </div>

      {/* Global command palette (Ctrl+K) — available on every app page */}
      <CommandPalette />

      {/* Global active processes banner — shows on ALL pages */}
      <ActiveProcessesBanner />
    </div>
  );
}
