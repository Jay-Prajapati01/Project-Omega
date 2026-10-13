"use client";

import { useMemo } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import {
  Search,
  Layers,
  Database,
  ArrowRight,
  Sparkles,
} from "lucide-react";

interface Props {
  query: string;
  chunksSearched: number;
  sourcesSearched: number;
  embeddingsScanned?: number;
  onSearch: (q: string) => void;
}

export function SearchNoResults({
  query,
  chunksSearched,
  sourcesSearched,
  embeddingsScanned,
  onSearch,
}: Props) {
  const router = useRouter();

  // Suggestions are real search terms derived from the user's own query —
  // never literal placeholder phrases like "Try a broader term".
  const suggestions = useMemo(() => {
    const words = Array.from(
      new Set(
        query
          .toLowerCase()
          .replace(/[^\p{L}\p{N}\s]/gu, " ")
          .split(/\s+/)
          .filter((w) => w.length > 2)
      )
    );
    const out: string[] = [];
    if (words.length > 1) out.push(words[0]);
    if (words.length > 2) out.push(words.slice(0, 2).join(" "));
    if (words.length > 3) out.push(words.slice(-2).join(" "));
    if (words.length === 1 && words[0]) out.push(words[0]);
    return out.slice(0, 3);
  }, [query]);

  const stats = [
    { icon: Layers, label: "Chunks", value: chunksSearched, color: "#FF5C00" },
    { icon: Database, label: "Sources", value: sourcesSearched, color: "#FF5C00" },
    ...(embeddingsScanned
      ? [{ icon: Layers, label: "Embeddings", value: embeddingsScanned, color: "#B96A00" }]
      : []),
  ];

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="flex flex-col items-center py-12"
    >
      <div className="mb-6 flex h-20 w-20 items-center justify-center rounded-[20px] bg-surface">
        <Search className="h-10 w-10 text-muted" />
      </div>

      <h2 className="mb-2 text-[18px] font-bold text-foreground">
        No exact semantic matches found
      </h2>
      <p className="mb-6 max-w-md text-center text-[13px] text-muted">
        The AI searched through your knowledge base but couldn&apos;t find
        closely matching content. Here&apos;s what was scanned:
      </p>

      <div className="mb-8 flex items-center gap-6 rounded-[14px] border-2 border-ink bg-card px-6 py-4">
        {stats.map((stat) => (
          <div key={stat.label} className="flex items-center gap-2">
            <div
              className="flex h-8 w-8 items-center justify-center rounded-lg"
              style={{ backgroundColor: `${stat.color}15` }}
            >
              <stat.icon className="h-4 w-4" style={{ color: stat.color }} />
            </div>
            <div>
              <div className="text-[14px] font-bold text-foreground">
                {stat.value}
              </div>
              <div className="text-[10px] text-muted">{stat.label}</div>
            </div>
          </div>
        ))}
      </div>

      {suggestions.length > 0 && (
        <div className="mb-8 w-full max-w-sm space-y-2">
          <h3 className="mb-3 text-[11px] font-semibold uppercase tracking-wider text-muted">
            Try one of these
          </h3>
          {suggestions.map((s) => (
            <button
              key={s}
              onClick={() => onSearch(s)}
              className="flex w-full items-center gap-3 rounded-[12px] border-2 border-ink bg-surface p-3 text-left text-[12px] text-foreground-3 transition-all hover:bg-surface hover:text-foreground"
            >
              <ArrowRight className="h-3.5 w-3.5 text-muted" />
              {s}
            </button>
          ))}
        </div>
      )}

      <motion.button
        whileHover={{ scale: 1.01 }}
        whileTap={{ scale: 0.99 }}
        onClick={() => router.push(`/chat?q=${encodeURIComponent(query)}`)}
        className="flex items-center gap-2 rounded-[14px] bg-[#FF5C00] border-2 border-ink px-5 py-3 text-[13px] font-semibold text-ink transition-all hover:bg-[#E14E00]"
      >
        <Sparkles className="h-4 w-4" />
        Ask AI instead
      </motion.button>
    </motion.div>
  );
}
