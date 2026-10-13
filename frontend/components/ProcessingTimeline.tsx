"use client";

import { useMemo } from "react";
import { Badge, Card } from "@/components/ui";
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

interface ProcessingTimelineProps {
  steps: StepConfig[];
  events: SSEEvent[];
  isStreaming: boolean;
  error: string | null;
}

function getIcon(icon: string): string {
  const icons: Record<string, string> = {
    link: "🔗",
    info: "📋",
    subtitles: "💬",
    brain: "🧠",
    scissors: "✂️",
    vector: "📊",
    database: "💾",
    play: "▶️",
    headphones: "🎧",
    globe: "🌐",
    upload: "📤",
    scan: "🔍",
    file: "📄",
    search: "🔎",
    load: "⏳",
    mic: "🎤",
    document: "📝",
  };
  return icons[icon] || "⚙️";
}

function StepCard({ step, state, isLast, isIdle = false }: { step: StepConfig; state: StepState; isLast: boolean; isIdle?: boolean }) {
  const statusColors = {
    pending: isIdle ? "border-border/50 bg-surface/30" : "border-border bg-surface/50",
    active: "border-brand/40 bg-brand-soft/40 shadow-sm",
    complete: "border-success/30 bg-success/10",
    error: "border-danger/30 bg-danger/10",
  };

  const statusIcons = {
    pending: (
      <div className={`rounded-full border-2 ${isIdle ? "border-border bg-surface/50 h-4 w-4" : "border-subtle h-5 w-5"}`} />
    ),
    active: (
      <div className="relative h-5 w-5">
        <div className="absolute inset-0 rounded-full border-2 border-brand animate-ping opacity-30" />
        <div className="absolute inset-0 rounded-full border-2 border-brand bg-brand-soft" />
        <div className="absolute inset-1.5 rounded-full bg-brand" />
      </div>
    ),
    complete: (
      <div className="flex h-5 w-5 items-center justify-center rounded-full bg-success">
        <svg className="h-3 w-3 text-ink" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
        </svg>
      </div>
    ),
    error: (
      <div className="flex h-5 w-5 items-center justify-center rounded-full bg-danger">
        <svg className="h-3 w-3 text-ink" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </div>
    ),
  };

  return (
    <div className="relative flex gap-4">
      {/* Vertical line */}
      {!isLast && (
        <div className="absolute left-[9px] top-6 h-full w-0.5">
          <div
            className={`h-full w-full transition-all duration-500 ${
              isIdle
                ? "bg-border"
                : state.status === "complete"
                ? "bg-success"
                : state.status === "active"
                ? "bg-gradient-to-b from-brand to-border"
                : "bg-border"
            }`}
          />
        </div>
      )}

      {/* Status icon */}
      <div className="relative z-10 mt-1 flex-shrink-0">
        {statusIcons[state.status]}
      </div>

      {/* Step content */}
      <div className={`mb-4 flex-1 rounded-lg border p-3 transition-all duration-300 ${statusColors[state.status]}`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-sm">{getIcon(step.icon)}</span>
            <span className={`text-sm font-medium ${
              isIdle
                ? "text-muted"
                : state.status === "complete"
                ? "text-foreground font-semibold"
                : state.status === "active"
                ? "text-brand font-semibold"
                : state.status === "error"
                ? "text-danger font-semibold"
                : "text-foreground-3"
            }`}>
              {step.name}
            </span>
          </div>
          {state.durationMs !== undefined && (
            <span className="text-xs text-muted">
              {(state.durationMs / 1000).toFixed(1)}s
            </span>
          )}
        </div>

        {/* Active step details */}
        {state.status === "active" && (
          <div className="mt-2">
            <p className="text-xs text-foreground-3">{step.description}</p>
            {state.subText && (
              <p className="mt-1 text-xs text-brand">{state.subText}</p>
            )}
            {state.progress !== undefined && (
              <div className="mt-2">
                <div className="flex items-center justify-between text-xs text-muted">
                  <span>{state.subText || "Progress"}</span>
                  <span>{state.progress}%</span>
                </div>
                <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-surface-muted">
                  <div
                    className="h-full rounded-full bg-brand transition-all duration-300"
                    style={{ width: `${state.progress}%` }}
                  />
                </div>
              </div>
            )}
          </div>
        )}

        {/* Error state */}
        {state.status === "error" && state.error && (
          <p className="mt-1 text-xs text-danger font-medium">{state.error}</p>
        )}

        {/* Preview (thumbnail, text) */}
        {state.preview && state.status === "complete" && (
          <PreviewCard preview={state.preview} stepId={step.id} />
        )}
      </div>
    </div>
  );
}

function PreviewCard({ preview, stepId }: { preview: Record<string, any>; stepId: string }) {
  if (stepId === "metadata" && preview.thumbnail) {
    return (
      <div className="mt-2 rounded-lg border-2 border-ink bg-surface p-2">
        <div className="flex gap-3">
          <img
            src={preview.thumbnail}
            alt={preview.title || "Thumbnail"}
            className="h-16 w-28 rounded object-cover"
          />
          <div className="min-w-0 flex-1">
            <p className="truncate text-xs font-medium text-foreground">{preview.title}</p>
            <p className="text-xs text-foreground-3">{preview.channel}</p>
            {preview.duration && (
              <p className="text-xs text-muted">
                {Math.floor(preview.duration / 60)}:{(preview.duration % 60).toString().padStart(2, "0")}
              </p>
            )}
          </div>
        </div>
      </div>
    );
  }

  if (preview.text) {
    return (
      <div className="mt-2 rounded-lg border-2 border-ink bg-surface p-2">
        <p className="text-xs leading-relaxed text-foreground-2 line-clamp-3">
          {preview.text}
        </p>
        {preview.chars && (
          <p className="mt-1 text-xs text-muted">
            {preview.chars.toLocaleString()} characters
          </p>
        )}
      </div>
    );
  }

  if (preview.chunk_count !== undefined) {
    return (
      <div className="mt-2 flex items-center gap-2">
        <Badge>{preview.chunk_count} chunks</Badge>
        {preview.vectors_count !== undefined && (
          <Badge>{preview.vectors_count} vectors</Badge>
        )}
      </div>
    );
  }

  return null;
}

export function ProcessingTimeline({
  steps,
  events,
  isStreaming,
  error,
}: ProcessingTimelineProps) {
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
          states[stepId] = {
            ...states[stepId],
            status: "active",
            subText: d.description,
          };
          break;

        case "step_progress":
          if (states[stepId].status === "active") {
            states[stepId] = {
              ...states[stepId],
              progress: d.progress,
              subText: d.sub_text || states[stepId].subText,
            };
          }
          break;

        case "step_complete": {
          const cumulative = typeof d.duration_ms === "number" ? d.duration_ms : 0;
          const perStep = Math.max(0, cumulative - prevCumulativeMs);
          prevCumulativeMs = Math.max(prevCumulativeMs, cumulative);
          states[stepId] = {
            ...states[stepId],
            status: "complete",
            progress: 100,
            durationMs: perStep,
            preview: Object.fromEntries(
              Object.entries(d).filter(([k]) => k !== "step" && k !== "duration_ms")
            ),
          };
          break;
        }

        case "step_fail":
          states[stepId] = {
            ...states[stepId],
            status: "error",
            error: d.error,
          };
          break;

        case "preview": {
          const typeMap: Record<string, string> = {
            thumbnail: "metadata",
            transcript: "transcript",
          };
          const targetStepId = d.type ? typeMap[d.type] : null;
          const effectiveId = targetStepId && states[targetStepId] ? targetStepId : stepId;
          states[effectiveId] = {
            ...states[effectiveId],
            preview: d,
          };
          break;
        }
      }
    }

    return states;
  }, [steps, events, error]);

  const overallProgress = useMemo(() => {
    let total = 0;
    let completed = 0;
    for (const step of steps) {
      total += step.weight;
      const state = stepStates[step.id];
      if (state.status === "complete") {
        completed += step.weight;
      } else if (state.status === "active" && state.progress !== undefined) {
        completed += (step.weight * state.progress) / 100;
      }
    }
    return total > 0 ? Math.round((completed / total) * 100) : 0;
  }, [steps, stepStates]);

  const isIdle = !isStreaming && events.length === 0 && !error;

  return (
    <Card className="mt-4">
      {/* Overall progress header */}
      <div className="mb-4">
        <div className="flex items-center justify-between text-sm">
          <span className="font-medium text-foreground">
            {isIdle ? "Pipeline Overview" : isStreaming ? "Processing..." : error ? "Failed" : "Complete"}
          </span>
          <span className="text-foreground-3">
            {isIdle ? `${steps.length} steps` : `${overallProgress}%`}
          </span>
        </div>
        {!isIdle && (
          <div className="mt-2 h-2 overflow-hidden rounded-full bg-surface">
            <div
              className={`h-full rounded-full transition-all duration-500 ${
                error
                  ? "bg-danger"
                  : overallProgress === 100
                  ? "bg-success"
                  : "bg-brand"
              }`}
              style={{ width: `${overallProgress}%` }}
            />
          </div>
        )}
      </div>

      {/* Timeline steps */}
      <div className="space-y-0">
        {steps.map((step, i) => (
          <StepCard
            key={step.id}
            step={step}
            state={stepStates[step.id]}
            isLast={i === steps.length - 1}
            isIdle={isIdle}
          />
        ))}
      </div>
    </Card>
  );
}
