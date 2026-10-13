"use client";

import { useRef, useEffect, KeyboardEvent } from "react";
import { motion } from "framer-motion";
import {
  Search,
  Mic,
  X,
  ArrowRight,
  Sparkles,
  Command,
} from "lucide-react";

interface Props {
  query: string;
  setQuery: (q: string) => void;
  onSearch: () => void;
  loading: boolean;
  placeholder?: string;
}

export function EnhancedSearchBar({
  query,
  setQuery,
  onSearch,
  loading,
  placeholder = "Ask anything across your knowledge...",
}: Props) {
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };
    document.addEventListener("keydown", handler as any);
    return () => document.removeEventListener("keydown", handler as any);
  }, []);

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && query.trim()) {
      onSearch();
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.1 }}
      className="relative"
    >
      <div className="group relative flex items-center rounded-[16px] border-2 border-ink bg-card transition-all duration-300 focus-within:border-[#FF5C00]/50 focus-within:shadow-[0_0_0_3px_rgba(255,92,0,0.15),0_0_30px_rgba(255,92,0,0.1)]">
        <div className="flex h-16 items-center pl-5">
          <Search className="h-5 w-5 text-muted transition-colors group-focus-within:text-[#FF5C00]" />
        </div>

        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          size={1}
          className="h-16 min-w-0 flex-1 bg-transparent px-4 text-[15px] font-normal text-foreground placeholder:text-muted outline-none"
        />

        {query && (
          <button
            onClick={() => setQuery("")}
            className="mr-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-muted transition-colors hover:bg-surface hover:text-foreground"
            aria-label="Clear search"
          >
            <X className="h-4 w-4" />
          </button>
        )}

        <button
          className="mr-1 hidden h-8 w-8 shrink-0 items-center justify-center rounded-lg text-muted transition-colors hover:bg-surface hover:text-foreground sm:flex"
          title="Voice search"
          aria-label="Voice search"
        >
          <Mic className="h-4 w-4" />
        </button>

        <button
          onClick={() => query.trim() && onSearch()}
          disabled={!query.trim() || loading}
          className="mr-2 flex h-10 shrink-0 items-center gap-2 rounded-[12px] bg-[#FF5C00] border-2 border-ink px-3 text-[13px] font-semibold text-ink transition-all hover:bg-[#E14E00] disabled:opacity-40 disabled:cursor-not-allowed sm:px-5"
          aria-label="Run search"
        >
          {loading ? (
            <div className="h-4 w-4 animate-spin rounded-full border-2 border-border border-t-white" />
          ) : (
            <Sparkles className="h-4 w-4" />
          )}
          <span className="hidden sm:inline">Search</span>
        </button>

        <div className="mr-4 hidden shrink-0 items-center gap-1 rounded-md bg-surface px-2.5 py-1.5 sm:flex">
          <Command className="h-3 w-3 text-muted" />
          <span className="text-[11px] font-medium text-muted">K</span>
        </div>
      </div>
    </motion.div>
  );
}
