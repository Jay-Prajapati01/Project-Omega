"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import {
  Home,
  MessageSquare,
  Youtube,
  Instagram,
  LayoutGrid,
  Network,
  Library,
  Settings,
  UserRound,
  PanelLeftClose,
  PanelLeftOpen,
  Activity,
  KeyRound,
} from "lucide-react";
import { ThemeToggle } from "./ThemeToggle";
import { useAuth } from "./CloudAuthGate";
import { getEntitlement } from "@/lib/commerce";

const links = [
  { href: "/dashboard", label: "Dashboard", icon: Home },
  { href: "/workspace", label: "Workspace", icon: LayoutGrid },
  { href: "/youtube", label: "YouTube", icon: Youtube },
  { href: "/instagram", label: "Instagram", icon: Instagram },
  { href: "/chat", label: "Ask AI", icon: MessageSquare },
  { href: "/graph", label: "Knowledge Graph", icon: Network },
  { href: "/stored", label: "Stored", icon: Library },
  { href: "/profile", label: "Profile", icon: UserRound },
  { href: "/settings", label: "Settings", icon: Settings },
];

const iconBtn =
  "rounded-lg border-2 border-transparent p-1.5 text-foreground-3 transition-colors hover:border-ink hover:bg-surface hover:text-foreground";

export function Nav({
  onNavigate,
  collapsed = false,
  onToggleCollapse,
}: {
  onNavigate?: () => void;
  collapsed?: boolean;
  onToggleCollapse?: () => void;
}) {
  const pathname = usePathname();
  const { session } = useAuth();
  const [isAdmin, setIsAdmin] = useState(false);
  const userId = session?.user.id;
  useEffect(() => {
    let mounted = true;
    if (!userId) {
      setIsAdmin(false);
      return;
    }
    getEntitlement()
      .then((entitlement) => {
        if (mounted) setIsAdmin(entitlement.role === "owner" || entitlement.role === "admin");
      })
      .catch(() => { if (mounted) setIsAdmin(false); });
    return () => { mounted = false; };
  }, [userId]);
  const visibleLinks = isAdmin
    ? [...links, { href: "/admin", label: "Admin & Analytics", icon: Activity }, { href: "/admin/api-key-analytics", label: "API Key Analytics", icon: KeyRound }]
    : links;
  const name = typeof session?.user.user_metadata?.preferred_name === "string" ? session.user.user_metadata.preferred_name : typeof session?.user.user_metadata?.full_name === "string" ? session.user.user_metadata.full_name : session?.user.email?.split("@")[0];
  return (
    <aside
      className={`flex h-full shrink-0 flex-col overflow-y-auto border-r-2 border-ink bg-card text-foreground transition-[width] duration-200 ${
        collapsed ? "w-16 px-2 py-4" : "w-56 p-4"
      }`}
    >
      {collapsed ? (
        <div className="mb-6 flex flex-col items-center gap-2">
          <Link
            href="/"
            onClick={onNavigate}
            title="Back to landing page"
            className="grid h-9 w-9 place-items-center overflow-hidden rounded-lg border-2 border-ink bg-[#111]"
          >
            <Image src="/logo.png" alt="" width={36} height={36} className="h-full w-full object-contain p-1" />
          </Link>
          <div className="flex flex-col items-center gap-1">
            <ThemeToggle className={iconBtn} />
            {onToggleCollapse && (
              <button
                type="button"
                onClick={onToggleCollapse}
                aria-label="Expand sidebar"
                title="Expand sidebar"
                className={iconBtn}
              >
                <PanelLeftOpen className="h-4 w-4" />
              </button>
            )}
          </div>
        </div>
      ) : (
        <div className="mb-8 flex items-center gap-2 px-2">
          <Link
            href="/"
            onClick={onNavigate}
            title="Back to landing page"
            className="flex items-center gap-2 rounded-lg"
          >
            <span className="grid h-9 w-9 place-items-center overflow-hidden rounded-lg border-2 border-ink bg-[#111]">
              <Image src="/logo.png" alt="" width={36} height={36} className="h-full w-full object-contain p-1" />
            </span>
            <span className="text-lg font-extrabold tracking-tight text-foreground">MindMesh</span>
          </Link>
          <div className="ml-auto flex flex-col items-center gap-1">
            <ThemeToggle className={iconBtn} />
            {onToggleCollapse && (
              <button
                type="button"
                onClick={onToggleCollapse}
                aria-label="Collapse sidebar"
                title="Collapse sidebar"
                className={iconBtn}
              >
                <PanelLeftClose className="h-4 w-4" />
              </button>
            )}
          </div>
        </div>
      )}
      <nav className="w-full space-y-1.5">
        {visibleLinks.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || pathname.startsWith(`${href}/`);
          return (
            <Link
              key={href}
              href={href}
              onClick={onNavigate}
              title={collapsed ? label : undefined}
              className={`flex rounded-xl text-sm font-bold transition-all ${
                collapsed ? "justify-center px-0 py-2" : "items-center gap-3 px-3 py-2"
              } ${
                active
                  ? "brut-btn bg-brand text-ink font-extrabold"
                  : "border-2 border-transparent text-foreground-3 hover:border-ink hover:bg-surface hover:text-foreground"
              }`}
            >
              <Icon className="h-4 w-4 shrink-0" />
              {!collapsed && label}
            </Link>
          );
        })}
      </nav>
      <Link
        href="/profile"
        onClick={onNavigate}
        title={collapsed ? "Your profile" : undefined}
        className={`mt-auto w-full rounded-xl border-2 border-ink bg-surface hover:bg-paper-card ${
          collapsed ? "flex justify-center p-2" : "flex items-center gap-3 p-3"
        }`}
      >
        <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-orange font-bold">{name?.slice(0, 1).toUpperCase() || <UserRound className="h-4 w-4" />}</span>
        {!collapsed && (
          <span className="min-w-0">
            <span className="block truncate text-sm font-bold">{name || "Your profile"}</span>
            <span className="block text-xs text-muted">Account settings</span>
          </span>
        )}
      </Link>
    </aside>
  );
}
