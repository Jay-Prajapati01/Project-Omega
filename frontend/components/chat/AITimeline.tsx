"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Brain,
  Check,
  Loader2,
  Search,
  Network,
  Zap,
  ChevronDown,
  ChevronUp,
  Clock,
} from "lucide-react";

interface Props {
  loading: boolean;
  chunksSearched: number;
  sourcesSearched: number;
  searchTimeMs: number;
  completedSteps: number;
}

const PIPELINE_STEPS = [
  { label: "Query Embedded", icon: Search, detail: "Vector embedding via Ollama" },
  { label: "Chunks Retrieved", icon: Brain, detail: "Top-K cosine similarity" },
  { label: "Sources Filtered", icon: Network, detail: "Ranked by relevance" },
  { label: "Context Assembled", icon: Zap, detail: "Passages + citations" },
  { label: "Answer Generated", icon: Check, detail: "LLM grounded response" },
];

export function AITimeline({
  loading,
  chunksSearched,
  sourcesSearched,
  searchTimeMs,
  completedSteps,
}: Props) {
  const [expanded, setExpanded] = useState(false);

  if (!loading && completedSteps === 0) return null;

  return (
    <motion.div
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: "auto" }}
      exit={{ opacity: 0, height: 0 }}
      className="overflow-hidden rounded-[14px] border-2 border-ink bg-card"
    >
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full flex-wrap items-center justify-between gap-2 px-5 py-3"
      >
        <div className="flex min-w-0 flex-wrap items-center gap-3">
          <div className="flex h-6 w-6 items-center justify-center rounded-md bg-[#FF5C00]/15">
            <Brain className="h-3.5 w-3.5 text-[#FF5C00]" />
          </div>
          <span className="text-[12px] font-semibold text-foreground-3">
            {loading ? "AI Reasoning..." : "AI Reasoning Complete"}
          </span>
          {!loading && (
            <span className="flex items-center gap-1 rounded-full bg-[#FF5C00]/10 px-2 py-0.5 text-[10px] font-medium text-[#FF5C00]">
              <Check className="h-3 w-3" />
              Done
            </span>
          )}
        </div>
        <div className="flex min-w-0 flex-wrap items-center gap-3">
          {!loading && searchTimeMs > 0 && (
            <div className="flex items-center gap-2 text-[10px] text-muted">
              <span className="flex items-center gap-1">
                <Clock className="h-3 w-3" />
                {searchTimeMs >= 1000
                  ? `${(searchTimeMs / 1000).toFixed(1)}s`
                  : `${searchTimeMs}ms`}
              </span>
              <span>•</span>
              <span>{chunksSearched} chunks</span>
              <span>•</span>
              <span>{sourcesSearched} sources</span>
            </div>
          )}
          {expanded ? (
            <ChevronUp className="h-4 w-4 text-muted" />
          ) : (
            <ChevronDown className="h-4 w-4 text-muted" />
          )}
        </div>
      </button>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden border-t-2 border-ink"
          >
            <div className="space-y-1 px-5 py-3">
              {PIPELINE_STEPS.map((step, i) => {
                const done = i < completedSteps;
                const active = i === completedSteps && loading;
                const Icon = step.icon;

                return (
                  <motion.div
                    key={step.label}
                    initial={{ opacity: 0, x: -8 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.08 }}
                    className="flex items-center gap-3 py-1.5"
                  >
                    <div className="flex items-center gap-2">
                      {done ? (
                        <div className="flex h-5 w-5 items-center justify-center rounded-full bg-[#FF5C00]/15">
                          <Check className="h-3 w-3 text-[#FF5C00]" />
                        </div>
                      ) : active ? (
                        <div className="flex h-5 w-5 items-center justify-center">
                          <Loader2 className="h-3.5 w-3.5 animate-spin text-[#FF5C00]" />
                        </div>
                      ) : (
                        <div className="flex h-5 w-5 items-center justify-center rounded-full bg-surface">
                          <Icon className="h-3 w-3 text-muted" />
                        </div>
                      )}
                      <span
                        className={`text-[12px] font-medium ${
                          done ? "text-[#FF5C00]" : active ? "text-[#FF5C00]" : "text-muted"
                        }`}
                      >
                        {step.label}
                      </span>
                    </div>
                    <span className="text-[10px] text-muted">{step.detail}</span>
                    {done && loading === false && i === completedSteps - 1 && searchTimeMs > 0 && (
                      <span className="ml-auto text-[10px] text-[#FF5C00]">
                        {searchTimeMs >= 1000
                          ? `${(searchTimeMs / 1000).toFixed(1)}s total`
                          : `${searchTimeMs}ms total`}
                      </span>
                    )}
                  </motion.div>
                );
              })}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
