"use client";

import { useMemo, useState } from "react";
import { SSEEvent } from "@/hooks/useSSE";

interface StepConfig {
  id: string;
  name: string;
  icon: string;
  description: string;
  weight: number;
}

interface StepState {
  status: "pending" | "active" | "complete" | "error";
  progress?: number;
  subText?: string;
  preview?: Record<string, any>;
  durationMs?: number;
  error?: string;
}

interface PipelineTimelineProps {
  steps: StepConfig[];
  events: SSEEvent[];
  isStreaming: boolean;
  error: string | null;
  isIdle: boolean;
}

const STEP_ICONS: Record<string, { emoji: string; color: string }> = {
  link: { emoji: "🔗", color: "#B96A00" },
  info: { emoji: "📋", color: "#FF5C00" },
  subtitles: { emoji: "💬", color: "#B96A00" },
  brain: { emoji: "🧠", color: "#FF5C00" },
  scissors: { emoji: "✂️", color: "#F59E0B" },
  vector: { emoji: "📊", color: "#FF5C00" },
  database: { emoji: "💾", color: "#FF5C00" },
  play: { emoji: "▶️", color: "#FF5C00" },
  headphones: { emoji: "🎧", color: "#F59E0B" },
  globe: { emoji: "🌐", color: "#B96A00" },
  upload: { emoji: "📤", color: "#FF5C00" },
  scan: { emoji: "🔍", color: "#F59E0B" },
  file: { emoji: "📄", color: "#6B5B4D" },
  search: { emoji: "🔎", color: "#B96A00" },
  load: { emoji: "⏳", color: "#6B5B4D" },
  mic: { emoji: "🎤", color: "#F59E0B" },
  document: { emoji: "📝", color: "#FF5C00" },
};

function StepIcon({ icon, status }: { icon: string; status: StepState["status"] }) {
  const cfg = STEP_ICONS[icon] || { emoji: "⚙️", color: "#6B5B4D" };

  if (status === "complete") {
    return (
      <div className="relative flex h-10 w-10 items-center justify-center">
        <div className="absolute inset-0 rounded-full bg-[#FF5C00]/20" />
        <svg className="relative h-5 w-5 text-[#FF5C00] animate-check-pop" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
        </svg>
      </div>
    );
  }

  if (status === "active") {
    return (
      <div className="relative flex h-10 w-10 items-center justify-center">
        <div className="absolute inset-0 rounded-full bg-[#FF5C00]/20 pulse-ring" />
        <div className="absolute inset-0 rounded-full bg-[#FF5C00]/10" />
        <span className="relative text-lg">{cfg.emoji}</span>
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className="relative flex h-10 w-10 items-center justify-center">
        <div className="absolute inset-0 rounded-full bg-danger/20" />
        <svg className="relative h-5 w-5 text-danger" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </div>
    );
  }

  return (
    <div className="flex h-10 w-10 items-center justify-center rounded-full border-2 border-ink bg-surface">
      <span className="text-sm opacity-40">{cfg.emoji}</span>
    </div>
  );
}

function ConnectorLine({ status, isIdle, isLast }: { status: StepState["status"]; isIdle: boolean; isLast: boolean }) {
  if (isLast) return <div className="w-px" />;

  return (
    <div className="relative mx-auto h-6 w-px">
      <div className="absolute inset-0 bg-surface" />
      <div
        className={`absolute inset-x-0 top-0 transition-all duration-700 ease-out ${
          status === "complete"
            ? "bg-[#FF5C00] h-full"
            : status === "active"
            ? "bg-gradient-to-b from-[#FF5C00] to-transparent h-full"
            : isIdle
            ? "bg-surface h-full"
            : "bg-surface h-0"
        }`}
      />
    </div>
  );
}

function StepPreview({ preview, stepId }: { preview: Record<string, any>; stepId: string }) {
  const [expanded, setExpanded] = useState(false);

  const hasContent = useMemo(() => {
    if (stepId === "metadata" && preview.thumbnail) return true;
    if (preview.text) return true;
    if (preview.chars !== undefined) return true;
    if (preview.chunk_count !== undefined) return true;
    if (preview.summary) return true;
    return false;
  }, [preview, stepId]);

  if (!hasContent) return null;

  return (
    <div className="mt-2 animate-fade-in">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center justify-between rounded-lg bg-surface px-3 py-2 text-[11px] text-foreground-3 transition hover:bg-surface"
      >
        <span>Preview</span>
        <svg className={`h-3 w-3 transition-transform ${expanded ? "rotate-180" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {expanded && (
        <div className="mt-1 animate-expand overflow-hidden">
          {stepId === "metadata" && preview.thumbnail && (
            <div className="flex gap-3 rounded-lg bg-surface p-3">
              <img src={preview.thumbnail} alt={preview.title ? `Preview image for ${preview.title}` : "Saved source preview image"} className="h-16 w-28 rounded-lg object-cover" />
              <div className="min-w-0 flex-1">
                <p className="truncate text-[12px] font-medium text-foreground">{preview.title}</p>
                <p className="text-[11px] text-muted">{preview.channel}</p>
                {preview.duration && <p className="text-[11px] text-muted">{Math.floor(preview.duration / 60)}:{(preview.duration % 60).toString().padStart(2, "0")}</p>}
              </div>
            </div>
          )}
          {preview.text && (
            <div className="rounded-lg bg-surface p-3">
              <p className="max-h-32 overflow-y-auto text-[11px] leading-relaxed text-foreground-3 whitespace-pre-wrap">{preview.text}</p>
            </div>
          )}
          {preview.chars !== undefined && !preview.text && (
            <div className="rounded-lg bg-surface p-3">
              <span className="text-[11px] tabular-nums text-muted">{preview.chars.toLocaleString()} characters</span>
            </div>
          )}
          {preview.chunk_count !== undefined && (
            <div className="flex gap-2 mt-1">
              <span className="rounded-full bg-surface px-2.5 py-1 text-[10px] tabular-nums text-foreground-3">{preview.chunk_count} chunks</span>
              {preview.vectors_count !== undefined && <span className="rounded-full bg-surface px-2.5 py-1 text-[10px] tabular-nums text-foreground-3">{preview.vectors_count} vectors</span>}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function StepRow({ step, state, isLast, isIdle, index }: { step: StepConfig; state: StepState; isLast: boolean; isIdle: boolean; index: number }) {
  const borderColor = {
    complete: "border-[#FF5C00]/15 bg-[#FF5C00]/[0.02]",
    active: "border-[#FF5C00]/25 bg-[#FF5C00]/[0.04] shadow-[0_0_20px_rgba(255,92,0,0.08)]",
    error: "border-danger/20 bg-danger/5",
    pending: isIdle ? "border-border bg-transparent" : "border-border bg-card",
  }[state.status];

  return (
    <div className="flex">
      {/* Icon column */}
      <div className="flex flex-col items-center w-10 flex-shrink-0">
        <StepIcon icon={step.icon} status={state.status} />
        <ConnectorLine status={state.status} isIdle={isIdle} isLast={isLast} />
      </div>

      {/* Content column */}
      <div className={`flex-1 ml-3 mb-1 rounded-[16px] border p-3.5 transition-all duration-300 ${borderColor}`}>
        {/* Top row: name + status */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className={`text-[13px] font-semibold ${
              isIdle ? "text-muted"
                : state.status === "complete" ? "text-[#FF5C00]"
                : state.status === "active" ? "text-foreground"
                : state.status === "error" ? "text-danger"
                : "text-foreground-3"
            }`}>
              {step.name}
            </span>
          </div>
          <div className="flex items-center gap-2">
            {state.status === "active" && state.progress !== undefined && (
              <span className="text-[11px] tabular-nums font-semibold text-[#FF5C00]">{state.progress}%</span>
            )}
            {state.status === "active" && (
              <span className="inline-flex items-center gap-1 rounded-full bg-[#FF5C00]/15 px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider text-[#FF5C00]">
                <span className="h-1 w-1 rounded-full bg-[#FF5C00] animate-pulse" />
                Running
              </span>
            )}
            {state.status === "complete" && state.durationMs !== undefined && (
              <span className="text-[11px] tabular-nums text-muted">{(state.durationMs / 1000).toFixed(1)}s</span>
            )}
            {state.status === "complete" && (
              <span className="inline-flex items-center gap-1 rounded-full bg-[#FF5C00]/15 px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider text-[#FF5C00]">
                ✓ Done
              </span>
            )}
            {state.status === "error" && (
              <span className="inline-flex items-center gap-1 rounded-full bg-danger/15 px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider text-danger">
                ✕ Failed
              </span>
            )}
            {state.status === "pending" && (
              <span className="text-[11px] text-muted">—</span>
            )}
          </div>
        </div>

        {/* Description (active or idle only) */}
        {(state.status === "active" || isIdle) && (
          <p className="mt-1 text-[11px] text-muted">{step.description}</p>
        )}

        {/* Progress bar (active) */}
        {state.status === "active" && state.progress !== undefined && (
          <div className="mt-2.5">
            <div className="h-[4px] overflow-hidden rounded-full bg-surface">
              <div
                className="h-full rounded-full bg-[#FF5C00] transition-all duration-500 progress-stripes"
                style={{ width: `${state.progress}%` }}
              />
            </div>
            {state.subText && <p className="mt-1.5 text-[10px] text-muted">{state.subText}</p>}
          </div>
        )}

        {/* Error */}
        {state.status === "error" && state.error && (
          <p className="mt-1.5 text-[11px] text-danger">{state.error}</p>
        )}

        {/* Expandable preview */}
        {state.status === "complete" && state.preview && (
          <StepPreview preview={state.preview} stepId={step.id} />
        )}
      </div>
    </div>
  );
}

export function PipelineTimeline({ steps, events, isStreaming, error, isIdle }: PipelineTimelineProps) {
  const stepStates = useMemo(() => {
    const states: Record<string, StepState> = {};
    for (const step of steps) {
      states[step.id] = { status: "pending" };
    }
    let prevCumulativeMs = 0;
    for (const evt of events) {
      const d = evt.data;
      const stepIdx = (d.step || 1) - 1;
      const stepId = steps[stepIdx]?.id;
      if (!stepId) continue;

      switch (evt.event) {
        case "step_start":
          states[stepId] = { ...states[stepId], status: "active", subText: d.description };
          break;
        case "step_progress":
          if (states[stepId].status === "active") {
            states[stepId] = { ...states[stepId], progress: d.progress, subText: d.sub_text || states[stepId].subText };
          }
          break;
        case "step_complete": {
          // Backend sends CUMULATIVE ms since the pipeline started; convert to
          // a per-step duration so the label and the total are both correct.
          const cumulative = typeof d.duration_ms === "number" ? d.duration_ms : 0;
          const perStep = Math.max(0, cumulative - prevCumulativeMs);
          prevCumulativeMs = Math.max(prevCumulativeMs, cumulative);
          states[stepId] = {
            ...states[stepId],
            status: "complete",
            progress: 100,
            durationMs: perStep,
            preview: Object.fromEntries(Object.entries(d).filter(([k]) => k !== "step" && k !== "duration_ms")),
          };
          break;
        }
        case "step_fail":
          states[stepId] = { ...states[stepId], status: "error", error: d.error };
          break;
      }
    }
    return states;
  }, [steps, events]);

  return (
    <div className="space-y-0">
      {steps.map((step, i) => (
        <StepRow
          key={step.id}
          step={step}
          state={stepStates[step.id]}
          isLast={i === steps.length - 1}
          isIdle={isIdle}
          index={i}
        />
      ))}
    </div>
  );
}
