"use client";

import { motion } from "framer-motion";
import {
  Brain,
  Sparkles,
  FileText,
  Globe,
  Clock,
  TrendingUp,
  Zap,
} from "lucide-react";
import { useAppStore } from "@/lib/store";

interface Props {
  onSearch: (q: string) => void;
}

const SUGGESTED_SEARCHES = [
  { icon: Brain, label: "What are the key insights from my notes?", color: "#FF5C00" },
  { icon: Sparkles, label: "Summarize my latest YouTube videos", color: "#FF5C00" },
  { icon: FileText, label: "What topics appear most in my PDFs?", color: "#E14E00" },
  { icon: Globe, label: "Find connections between my web articles", color: "#B96A00" },
];

const POPULAR_TOPICS = [
  "AI Agents",
  "Machine Learning",
  "Productivity",
  "Knowledge Graphs",
  "Note-taking",
  "Research",
  "Content Creation",
  "Developer Tools",
];

const TRENDING_ENTITIES = [
  "NotebookLM",
  "OpenAI",
  "Cursor",
  "LangChain",
  "Vector Database",
  "RAG",
];

export function SearchEmptyState({ onSearch }: Props) {
  const recentSearches = useAppStore((s) => s.recentSearches);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="flex flex-col items-center py-12"
    >
      <div className="mb-6 flex h-20 w-20 items-center justify-center rounded-[20px] bg-gradient-to-br from-[#FF5C00]/15 to-[#FF5C00]/5">
        <Brain className="h-10 w-10 text-[#FF5C00]" />
      </div>

      <h2 className="mb-2 text-[20px] font-bold text-foreground">
        Explore Your Intelligence
      </h2>
      <p className="mb-8 max-w-md text-center text-[13px] text-muted">
        Search across all your knowledge sources. Ask questions, find connections,
        and discover insights hidden in your data.
      </p>

      {/* Suggested Searches */}
      <div className="mb-8 w-full max-w-2xl">
        <h3 className="mb-3 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-muted">
          <Sparkles className="h-3.5 w-3.5 text-[#FF5C00]" />
          Suggested Searches
        </h3>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          {SUGGESTED_SEARCHES.map((suggestion) => (
            <motion.button
              key={suggestion.label}
              whileHover={{ scale: 1.01, y: -1 }}
              whileTap={{ scale: 0.99 }}
              onClick={() => onSearch(suggestion.label)}
              className="flex items-center gap-3 rounded-[14px] border-2 border-ink bg-card p-3.5 text-left transition-all hover:border-border hover:bg-surface"
            >
              <div
                className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-[10px]"
                style={{ backgroundColor: `${suggestion.color}15` }}
              >
                <suggestion.icon
                  className="h-4 w-4"
                  style={{ color: suggestion.color }}
                />
              </div>
              <span className="text-[12px] text-foreground-3">{suggestion.label}</span>
            </motion.button>
          ))}
        </div>
      </div>

      {/* Recent Searches */}
      {recentSearches.length > 0 && (
        <div className="mb-8 w-full max-w-2xl">
          <h3 className="mb-3 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-muted">
            <Clock className="h-3.5 w-3.5" />
            Recently Searched
          </h3>
          <div className="flex flex-wrap gap-2">
            {recentSearches.slice(0, 6).map((search) => (
              <button
                key={search}
                onClick={() => onSearch(search)}
                className="flex items-center gap-2 rounded-full border-2 border-ink bg-surface px-3.5 py-1.5 text-[11px] text-foreground-3 transition-all hover:bg-surface hover:text-foreground"
              >
                <Clock className="h-3 w-3 text-muted" />
                {search}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Popular Topics */}
      <div className="mb-8 w-full max-w-2xl">
        <h3 className="mb-3 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-muted">
          <TrendingUp className="h-3.5 w-3.5" />
          Popular Topics
        </h3>
        <div className="flex flex-wrap gap-2">
          {POPULAR_TOPICS.map((topic) => (
            <button
              key={topic}
              onClick={() => onSearch(topic)}
              className="rounded-full bg-surface px-3.5 py-1.5 text-[11px] text-muted transition-all hover:bg-[#FF5C00]/10 hover:text-[#FF5C00]"
            >
              {topic}
            </button>
          ))}
        </div>
      </div>

      {/* Trending Entities */}
      <div className="w-full max-w-2xl">
        <h3 className="mb-3 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-muted">
          <Zap className="h-3.5 w-3.5" />
          Trending Entities
        </h3>
        <div className="flex flex-wrap gap-2">
          {TRENDING_ENTITIES.map((entity) => (
            <button
              key={entity}
              onClick={() => onSearch(entity)}
              className="flex items-center gap-1.5 rounded-full border-2 border-ink bg-surface px-3.5 py-1.5 text-[11px] text-foreground-3 transition-all hover:border-[#FF5C00]/30 hover:bg-[#FF5C00]/10 hover:text-[#FF5C00]"
            >
              <Zap className="h-3 w-3 text-[#F59E0B]" />
              {entity}
            </button>
          ))}
        </div>
      </div>
    </motion.div>
  );
}
