"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Check, Loader2, Brain, Search, Network, Sparkles, Zap } from "lucide-react";
import { AnimatedCounter } from "./AnimatedCounter";

interface PipelineStep {
  label: string;
  detail: string;
  icon: typeof Brain;
}

interface Props {
  loading: boolean;
  chunksSearched?: number;
  sourcesSearched?: number;
  embeddingsScanned?: number;
  resultCount?: number;
  searchTimeMs?: number;
}

const PIPELINE_STEPS: PipelineStep[] = [
  { label: "Query Embedded", detail: "1024 dimensions", icon: Brain },
  { label: "Vector Search", detail: "scanning embeddings", icon: Search },
  { label: "AI Re-ranking", detail: "complete", icon: Sparkles },
  { label: "Knowledge Graph", detail: "expanded", icon: Network },
  { label: "Results Ranked", detail: "semantic matching", icon: Zap },
];

export function ReasoningStrip({
  loading,
  chunksSearched = 0,
  sourcesSearched = 0,
  embeddingsScanned = 0,
  resultCount = 0,
  searchTimeMs = 0,
}: Props) {
  const [completedSteps, setCompletedSteps] = useState<number>(0);

  useEffect(() => {
    if (!loading) {
      setCompletedSteps(PIPELINE_STEPS.length);
      return;
    }
    setCompletedSteps(0);
    const timers = PIPELINE_STEPS.map((_, i) =>
      setTimeout(() => setCompletedSteps(i + 1), (i + 1) * 250)
    );
    return () => timers.forEach(clearTimeout);
  }, [loading]);

  if (!loading && completedSteps === 0 && resultCount === 0) return null;

  return (
    <motion.div
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: "auto" }}
      exit={{ opacity: 0, height: 0 }}
      className="overflow-hidden rounded-[14px] border-2 border-ink bg-card"
    >
      <div className="flex flex-wrap items-center gap-x-6 gap-y-2 px-5 py-3">
        <div className="flex items-center gap-2">
          <Brain className="h-4 w-4 text-[#FF5C00]" />
          <span className="text-[11px] font-semibold uppercase tracking-wider text-foreground-3">
            AI Pipeline
          </span>
        </div>

        <div className="flex min-w-0 flex-1 flex-wrap items-center gap-1">
          {PIPELINE_STEPS.map((step, i) => {
            const done = i < completedSteps;
            const active = i === completedSteps && loading;
            const Icon = step.icon;

            return (
              <div key={step.label} className="flex items-center gap-1">
                <div className="flex items-center gap-1.5">
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
                    className={`text-[11px] font-medium ${
                      done
                        ? "text-[#FF5C00]"
                        : active
                        ? "text-[#FF5C00]"
                        : "text-muted"
                    }`}
                  >
                    {step.label}
                  </span>
                </div>
                {i < PIPELINE_STEPS.length - 1 && (
                  <div
                    className={`mx-1 h-px w-4 ${
                      done ? "bg-[#FF5C00]/30" : "bg-surface"
                    }`}
                  />
                )}
              </div>
            );
          })}
        </div>

        {!loading && resultCount > 0 && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex flex-wrap items-center gap-4 text-[11px]"
          >
            <span className="text-muted">
              <AnimatedCounter value={chunksSearched} /> chunks
            </span>
            <span className="text-muted">
              <AnimatedCounter value={sourcesSearched} /> sources
            </span>
            <span className="text-muted">
              <AnimatedCounter value={embeddingsScanned} /> embeddings
            </span>
            <span className="text-muted">
              Completed in <AnimatedCounter value={searchTimeMs} /> ms
            </span>
          </motion.div>
        )}

        {loading && (
          <span className="text-[11px] text-muted animate-pulse">
            Processing...
          </span>
        )}
      </div>
    </motion.div>
  );
}
