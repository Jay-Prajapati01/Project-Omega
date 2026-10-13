"use client";

import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { SSEEvent } from "@/hooks/useSSE";
import { getDetailedHealth } from "@/lib/api";

interface AnalyticsPanelProps {
  events: SSEEvent[];
  steps: { id: string; name: string }[];
  isStreaming: boolean;
  isIdle: boolean;
  startedAt: number;
}

interface Metric {
  label: string;
  value: string | number;
  icon: string;
  color?: string;
  bold?: boolean;
}

function AnimatedNumber({ value, duration = 500 }: { value: number; duration?: number }) {
  const [display, setDisplay] = useState(0);

  useEffect(() => {
    if (value === display) return;
    const start = display;
    const diff = value - start;
    const startTime = Date.now();
    const tick = () => {
      const elapsed = Date.now() - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplay(Math.round(start + diff * eased));
      if (progress < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }, [value, duration, display]);

  return <span className="tabular-nums">{display}</span>;
}

export function AnalyticsPanel({ events, steps, isStreaming, isIdle, startedAt }: AnalyticsPanelProps) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (!isStreaming) {
      if (startedAt > 0) setElapsed(Date.now() - startedAt);
      return;
    }
    const i = setInterval(() => setElapsed(Date.now() - startedAt), 100);
    return () => clearInterval(i);
  }, [isStreaming, startedAt]);

  const { data: health } = useQuery({
    queryKey: ["health", "detailed"],
    queryFn: getDetailedHealth,
    refetchInterval: 60000,
    retry: 1,
  });

  // Derived from the full event list — no accumulation, so tokens are never double-counted.
  const tokenCount = useMemo(
    () => events.filter((e) => e.event === "stream_token").length,
    [events]
  );

  const stats = useMemo(() => {
    let completedSteps = 0;
    let currentStepName = "";
    let chunks = 0;
    let vectors = 0;
    const isComplete = events.some((e) => e.event === "complete");

    for (const evt of events) {
      const d = evt.data;
      if (evt.event === "step_complete") {
        completedSteps++;
        if (d.chunk_count) chunks = d.chunk_count;
        if (d.vectors_count) vectors = d.vectors_count;
      }
      if (evt.event === "step_start") {
        const idx = (d.step || 1) - 1;
        currentStepName = steps[idx]?.name || "";
      }
    }

    if (isComplete) {
      currentStepName = "All steps completed";
      completedSteps = steps.length;
    }

    return { completedSteps, currentStepName, chunks, vectors };
  }, [events, steps]);

  const elapsedSecs = Math.floor(elapsed / 1000);
  const eta = stats.completedSteps > 0
    ? Math.ceil((elapsed / stats.completedSteps) * (steps.length - stats.completedSteps) / 1000)
    : 0;

  const checksOk = health
    ? Object.values(health.checks).every((v) => v === "ok")
    : false;

  const metrics: Metric[] = [
    { label: "Pipeline", value: isStreaming ? "Active" : isIdle ? "Ready" : "Done", icon: "⚡", color: isStreaming ? "text-[#FF5C00]" : isIdle ? "text-muted" : "text-[#FF5C00]", bold: true },
    { label: "Current Task", value: stats.currentStepName || (isIdle ? "Idle" : "Starting..."), icon: "📋" },
    { label: "Elapsed", value: `${elapsedSecs}s`, icon: "⏱️" },
    { label: "ETA", value: isStreaming && eta > 0 ? `~${eta}s` : "—", icon: "⏳" },
    { label: "Steps", value: `${stats.completedSteps}/${steps.length}`, icon: "📊" },
    { label: "Chunks", value: stats.chunks, icon: "📦" },
    { label: "Vectors", value: stats.vectors, icon: "🔢" },
    { label: "Tokens", value: tokenCount, icon: "🔤" },
    { label: "LLM", value: health?.llm_model ?? "—", icon: "🧠" },
    { label: "Embeddings", value: health?.embedding_model ?? "—", icon: "📐" },
    { label: "Vector DB", value: health?.collection ?? "—", icon: "💾" },
  ];

  return (
    <div className="rounded-[20px] border-2 border-ink bg-card p-4">
      {/* Header */}
      <div className="mb-3 flex items-center justify-between">
        <span className="text-[10px] font-bold uppercase tracking-wider text-muted">System Status</span>
        <div className="flex items-center gap-1.5">
          <span className={`h-1.5 w-1.5 rounded-full ${checksOk ? "bg-[#FF5C00]" : health ? "bg-[#F59E0B] animate-pulse" : "bg-muted"}`} />
          <span className="text-[10px] text-muted">
            {checksOk ? "Healthy" : health ? "Degraded" : "Unknown"}
          </span>
        </div>
      </div>

      {/* Metrics grid */}
      <div className="space-y-2">
        {metrics.map((m) => (
          <div key={m.label} className="flex items-center justify-between rounded-[8px] px-2 py-1.5 transition-colors hover:bg-surface">
            <div className="flex items-center gap-2">
              <span className="text-[11px]">{m.icon}</span>
              <span className="text-[10px] text-muted">{m.label}</span>
            </div>
            <span className={`text-[11px] tabular-nums ${m.bold ? "font-bold" : "font-medium"} ${m.color || "text-foreground-3"}`}>
              {typeof m.value === "number" ? <AnimatedNumber value={m.value} /> : m.value}
            </span>
          </div>
        ))}
      </div>

      {/* Progress ring */}
      <div className="mt-4 flex justify-center">
        <div className="relative h-20 w-20">
          <svg className="h-20 w-20 -rotate-90" viewBox="0 0 80 80">
            <circle cx="40" cy="40" r="34" fill="none" stroke="rgba(128,128,128,0.4)" strokeWidth="5" />
            <circle
              cx="40" cy="40" r="34" fill="none"
              stroke={isStreaming ? "#FF5C00" : stats.completedSteps === steps.length ? "#FF5C00" : "rgba(128,128,128,0.5)"}
              strokeWidth="5"
              strokeDasharray={`${2 * Math.PI * 34}`}
              strokeDashoffset={`${2 * Math.PI * 34 * (1 - (stats.completedSteps / steps.length))}`}
              strokeLinecap="round"
              className="transition-all duration-700 ease-out"
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-[14px] font-bold tabular-nums text-foreground">
              {Math.round((stats.completedSteps / steps.length) * 100)}%
            </span>
            <span className="text-[8px] text-muted">COMPLETE</span>
          </div>
        </div>
      </div>
    </div>
  );
}
