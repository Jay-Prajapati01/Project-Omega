"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useRouter } from "next/navigation";
import {
  Search,
  Youtube,
  Instagram,
  MessageSquare,
  Library,
  Settings,
  UserRound,
  Home,
  LayoutGrid,
  ArrowRight,
  History,
} from "lucide-react";
import { useAppStore } from "@/lib/store";

interface CommandItem {
  id: string;
  label: string;
  description?: string;
  icon: typeof Youtube;
  color: string;
  href?: string;
  action?: () => void;
  category: "navigation" | "action" | "search" | "recent";
  shortcut?: string;
}

const NAVIGATION_ITEMS: Omit<CommandItem, "category">[] = [
  { id: "dashboard", label: "Dashboard", description: "Mission Control Center", icon: Home, color: "var(--brand)", href: "/dashboard", shortcut: "⌘1" },
  { id: "workspace", label: "Workspace", description: "Notes and tools", icon: LayoutGrid, color: "var(--brand)", href: "/workspace" },
  { id: "chat", label: "Ask AI", description: "Chat with your knowledge", icon: MessageSquare, color: "var(--brand)", href: "/chat" },
  { id: "stored", label: "Stored", description: "Browse all sources", icon: Library, color: "var(--foreground-3)", href: "/stored" },
  { id: "profile", label: "Profile", description: "Manage your account profile", icon: UserRound, color: "var(--foreground-3)", href: "/profile" },
  { id: "settings", label: "Settings", description: "App configuration", icon: Settings, color: "var(--foreground-3)", href: "/settings" },
];

const ACTION_ITEMS: Omit<CommandItem, "category">[] = [
  { id: "add-youtube", label: "Add YouTube Video", description: "Extract & summarize video content", icon: Youtube, color: "#FF5C00", href: "/youtube" },
  { id: "add-instagram", label: "Add Instagram Reel", description: "Extract captions and on-screen text", icon: Instagram, color: "#FF5C00", href: "/instagram" },
  { id: "ask-ai", label: "Ask AI", description: "Ask across saved content", icon: MessageSquare, color: "var(--brand)", href: "/chat" },
  { id: "stored", label: "Open Stored", description: "Browse saved sources", icon: Library, color: "var(--foreground-3)", href: "/stored" },
];

export function CommandPalette() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  const open = useAppStore((s) => s.commandPaletteOpen);
  const setOpen = useAppStore((s) => s.setCommandPaletteOpen);
  const recentSearches = useAppStore((s) => s.recentSearches);

  const recentItems: CommandItem[] = recentSearches.slice(0, 3).map((q) => ({
    id: `recent-${q}`,
    label: q,
    icon: History,
    color: "var(--foreground-3)",
    category: "recent" as const,
    action: () => {
      setOpen(false);
      router.push(`/chat?q=${encodeURIComponent(q)}`);
    },
  }));

  const allItems: CommandItem[] = [
    ...NAVIGATION_ITEMS.map((item) => ({ ...item, category: "navigation" as const })),
    ...ACTION_ITEMS.map((item) => ({ ...item, category: "action" as const })),
    ...recentItems,
  ];

  const filtered = query
    ? allItems.filter(
        (item) =>
          item.label.toLowerCase().includes(query.toLowerCase()) ||
          item.description?.toLowerCase().includes(query.toLowerCase())
      )
    : allItems;

  const grouped = {
    navigation: filtered.filter((i) => i.category === "navigation"),
    action: filtered.filter((i) => i.category === "action"),
    recent: filtered.filter((i) => i.category === "recent"),
  };

  const flatFiltered = [...grouped.navigation, ...grouped.action, ...grouped.recent];

  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 50);
    } else {
      setQuery("");
    }
  }, [open]);

  const executeItem = useCallback(
    (item: CommandItem) => {
      if (item.action) {
        item.action();
      } else if (item.href) {
        setOpen(false);
        router.push(item.href);
      }
    },
    [router, setOpen]
  );

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setOpen(!open);
      }
      if (e.key === "Escape" && open) {
        setOpen(false);
      }
      // Numeric shortcuts shown on items (e.g. ⌘1) work while the palette is open
      if ((e.metaKey || e.ctrlKey) && /^[1-9]$/.test(e.key) && open) {
        const item = flatFiltered.find((i) => i.shortcut === `⌘${e.key}`);
        if (item) {
          e.preventDefault();
          executeItem(item);
        }
      }
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open, setOpen, flatFiltered, executeItem]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((i) => Math.min(i + 1, flatFiltered.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter" && flatFiltered[selectedIndex]) {
      executeItem(flatFiltered[selectedIndex]);
    }
  };

  useEffect(() => {
    const el = listRef.current?.querySelector(
      `[data-cmd-item="${selectedIndex}"]`
    );
    el?.scrollIntoView({ block: "nearest" });
  }, [selectedIndex]);

  if (!open) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-[100] flex items-start justify-center pt-[15vh]"
        onClick={() => setOpen(false)}
      >
        <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
        <motion.div
          initial={{ opacity: 0, scale: 0.96, y: -10 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.96, y: -10 }}
          transition={{ duration: 0.15 }}
          onClick={(e) => e.stopPropagation()}
          className="relative w-full max-w-[560px] overflow-hidden rounded-[16px] border-2 border-ink bg-card shadow-floating text-foreground"
        >
          <div className="flex items-center gap-3 border-b-2 border-ink px-4 py-3">
            <Search className="h-4 w-4 text-muted" />
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Search commands, pages, or actions..."
              className="flex-1 bg-transparent text-[14px] text-foreground placeholder-subtle outline-none"
            />
            <div className="flex items-center gap-1 rounded-md bg-surface px-2 py-1">
              <span className="text-[10px] text-muted">ESC</span>
            </div>
          </div>

          <div ref={listRef} className="max-h-[360px] overflow-y-auto p-2">
            {flatFiltered.length === 0 && (
              <div className="flex flex-col items-center py-8 text-center">
                <Search className="mb-2 h-6 w-6 text-subtle" />
                <p className="text-[12px] text-muted">No results found</p>
              </div>
            )}

            {grouped.navigation.length > 0 && (
              <div className="mb-1">
                <div className="px-2 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-subtle">
                  Navigation
                </div>
                {grouped.navigation.map((item, i) => {
                  const flatIndex = i;
                  const Icon = item.icon;
                  return (
                    <button
                      key={item.id}
                      data-cmd-item={flatIndex}
                      onClick={() => executeItem(item)}
                      onMouseEnter={() => setSelectedIndex(flatIndex)}
                      className={`flex w-full items-center gap-3 rounded-[10px] px-3 py-2.5 text-left transition-colors ${
                        selectedIndex === flatIndex
                          ? "bg-surface text-foreground"
                          : "text-foreground-2 hover:bg-surface/50"
                      }`}
                    >
                      <div
                        className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-[8px] bg-surface-muted"
                      >
                        <Icon className="h-4 w-4 text-brand" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-[13px] font-medium text-foreground">{item.label}</div>
                        {item.description && (
                          <div className="text-[11px] text-muted">{item.description}</div>
                        )}
                      </div>
                      {item.shortcut && (
                        <span className="text-[10px] text-subtle">{item.shortcut}</span>
                      )}
                      <ArrowRight className="h-3.5 w-3.5 text-subtle" />
                    </button>
                  );
                })}
              </div>
            )}

            {grouped.action.length > 0 && (
              <div className="mb-1">
                <div className="px-2 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-subtle">
                  Add Source
                </div>
                {grouped.action.map((item, i) => {
                  const flatIndex = grouped.navigation.length + i;
                  const Icon = item.icon;
                  return (
                    <button
                      key={item.id}
                      data-cmd-item={flatIndex}
                      onClick={() => executeItem(item)}
                      onMouseEnter={() => setSelectedIndex(flatIndex)}
                      className={`flex w-full items-center gap-3 rounded-[10px] px-3 py-2.5 text-left transition-colors ${
                        selectedIndex === flatIndex
                          ? "bg-surface text-foreground"
                          : "text-foreground-2 hover:bg-surface/50"
                      }`}
                    >
                      <div
                        className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-[8px] bg-surface-muted"
                      >
                        <Icon className="h-4 w-4" style={{ color: item.color }} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-[13px] font-medium text-foreground">{item.label}</div>
                        {item.description && (
                          <div className="text-[11px] text-muted">{item.description}</div>
                        )}
                      </div>
                      <ArrowRight className="h-3.5 w-3.5 text-subtle" />
                    </button>
                  );
                })}
              </div>
            )}

            {grouped.recent.length > 0 && (
              <div>
                <div className="px-2 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-subtle">
                  Recent Questions
                </div>
                {grouped.recent.map((item, i) => {
                  const flatIndex = grouped.navigation.length + grouped.action.length + i;
                  const Icon = item.icon;
                  return (
                    <button
                      key={item.id}
                      data-cmd-item={flatIndex}
                      onClick={() => executeItem(item)}
                      onMouseEnter={() => setSelectedIndex(flatIndex)}
                      className={`flex w-full items-center gap-3 rounded-[10px] px-3 py-2.5 text-left transition-colors ${
                        selectedIndex === flatIndex
                          ? "bg-surface text-foreground"
                          : "text-foreground-2 hover:bg-surface/50"
                      }`}
                    >
                      <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-[8px] bg-surface-muted">
                        <Icon className="h-4 w-4 text-muted" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-[13px] text-foreground-2">{item.label}</div>
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          <div className="flex items-center gap-4 border-t-2 border-ink px-4 py-2.5 text-subtle">
            <span className="flex items-center gap-1.5 text-[10px]">
              <span className="rounded bg-surface px-1.5 py-0.5 font-mono">↑↓</span>
              Navigate
            </span>
            <span className="flex items-center gap-1.5 text-[10px]">
              <span className="rounded bg-surface px-1.5 py-0.5 font-mono">↵</span>
              Select
            </span>
            <span className="flex items-center gap-1.5 text-[10px]">
              <span className="rounded bg-surface px-1.5 py-0.5 font-mono">ESC</span>
              Close
            </span>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
