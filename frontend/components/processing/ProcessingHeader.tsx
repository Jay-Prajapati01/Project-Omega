"use client";

import { useEffect, useMemo, useState } from "react";
import { Brain, X, Youtube, Instagram, FileText, Files, Mic, Globe } from "lucide-react";

interface ProcessingHeaderProps {
  sourceType: string;
  title: string;
  startedAt: number;
  totalSteps: number;
  completedSteps: number;
  activeStep: number;
  activeStepName: string;
  failedStep: number;
  isStreaming: boolean;
  onCancel: () => void;
  overallProgress: number;
}

const sourceIcons: Record<string, typeof Youtube> = {
  youtube: Youtube,
  instagram: Instagram,
  pdf: FileText,
  document: Files,
  audio: Mic,
  web: Globe,
};

function formatElapsed(ms: number): string {
  const secs = Math.floor(ms / 1000);
  const mins = Math.floor(secs / 60);
  const r = secs % 60;
  return mins > 0 ? `${mins}m ${r}s` : `${r}s`;
}

function ETA({ elapsed, completed, total }: { elapsed: number; completed: number; total: number }) {
  if (completed === 0 || total === 0) return <span>Calculating...</span>;
  const perStep = elapsed / completed;
  const remaining = Math.ceil(perStep * (total - completed));
  return <span>~{formatElapsed(remaining)} remaining</span>;
}

export function ProcessingHeader({
  sourceType,
  title,
  startedAt,
  totalSteps,
  completedSteps,
  activeStep,
  activeStepName,
  failedStep,
  isStreaming,
  onCancel,
  overallProgress,
}: ProcessingHeaderProps) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (!isStreaming) {
      // Show final elapsed when done
      if (startedAt > 0) setElapsed(Date.now() - startedAt);
      return;
    }
    const i = setInterval(() => setElapsed(Date.now() - startedAt), 100);
    return () => clearInterval(i);
  }, [isStreaming, startedAt]);

  const Icon = sourceIcons[sourceType] || Brain;
  const isComplete = overallProgress === 100 && !isStreaming && completedSteps === totalSteps;
  const isFailed = failedStep > 0;

  const displayTitle = useMemo(() => {
    if (!title) return sourceType;
    try {
      const u = new URL(title);
      return u.hostname.replace("www.", "");
    } catch {
      return title.length > 60 ? title.slice(0, 57) + "..." : title;
    }
  }, [title, sourceType]);

  return (
    <div className="rounded-[20px] border-2 border-ink bg-card p-5">
      {/* Top row */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          {/* Icon */}
          <div className={`relative flex h-11 w-11 items-center justify-center rounded-[14px] transition-all duration-500 ${
            isComplete ? "bg-[#FF5C00]/20" : isFailed ? "bg-danger/20" : "bg-[#FF5C00]/20"
          }`}>
            <Icon className={`h-5 w-5 transition-colors duration-500 ${
              isComplete ? "text-[#FF5C00]" : isFailed ? "text-danger" : "text-[#FF5C00]"
            }`} />
            {isStreaming && (
              <span className="absolute -right-1 -top-1 flex h-3 w-3">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[#FF5C00] opacity-40" />
                <span className="relative inline-flex h-3 w-3 rounded-full bg-[#FF5C00]" />
              </span>
            )}
          </div>
          {/* Title & meta */}
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-[15px] font-bold text-foreground tracking-tight">
                {isComplete ? "Processing Complete" : isFailed ? "Processing Failed" : "Processing"} {displayTitle}
              </h2>
              {isStreaming && (
                <span className="inline-flex items-center gap-1 rounded-full bg-[#FF5C00]/15 px-2 py-0.5 text-[10px] font-semibold text-[#FF5C00]">
                  <span className="h-1 w-1 rounded-full bg-[#FF5C00] animate-pulse" />
                  LIVE
                </span>
              )}
              {isComplete && (
                <span className="inline-flex items-center gap-1 rounded-full bg-[#FF5C00]/15 px-2 py-0.5 text-[10px] font-semibold text-[#FF5C00]">
                  ✓ DONE
                </span>
              )}
            </div>
            <div className="mt-0.5 flex items-center gap-3 text-[12px] text-muted">
              <span>{formatElapsed(elapsed)} elapsed</span>
              <span className="text-foreground-3">·</span>
              {isStreaming ? (
                <ETA elapsed={elapsed} completed={completedSteps} total={totalSteps} />
              ) : isComplete ? (
                <span>Completed in {formatElapsed(elapsed)}</span>
              ) : (
                <span>{completedSteps}/{totalSteps} steps</span>
              )}
              <span className="text-foreground-3">·</span>
              <span className={isStreaming ? "text-[#FF5C00]" : isFailed ? "text-danger" : isComplete ? "text-[#FF5C00]" : "text-muted"}>
                {isStreaming ? activeStepName || "Starting..." : isFailed ? `Failed at step ${failedStep}` : isComplete ? "All steps done" : "Idle"}
              </span>
            </div>
          </div>
        </div>

        {/* Cancel / status */}
        <div className="flex items-center gap-3">
          {isStreaming && (
            <button
              onClick={onCancel}
              className="flex items-center gap-2 brut-btn bg-danger px-4 py-2 text-[13px] font-bold text-card transition-all"
            >
              <X className="h-3.5 w-3.5" />
              Cancel
            </button>
          )}
        </div>
      </div>

      {/* Progress bar */}
      <div className="mt-4">
        <div className="relative h-[6px] overflow-hidden rounded-full bg-surface">
          <div
            className={`absolute inset-y-0 left-0 rounded-full transition-all duration-700 ease-out ${
              isFailed ? "bg-danger" : isComplete ? "bg-[#FF5C00]" : "bg-[#FF5C00]"
            } ${isStreaming && !isComplete && !isFailed ? "progress-stripes" : ""}`}
            style={{ width: `${overallProgress}%` }}
          />
        </div>
        <div className="mt-2 flex items-center justify-between">
          <div className="flex items-center gap-4 text-[11px]">
            <span className="tabular-nums font-semibold text-foreground">{overallProgress}%</span>
            <span className="text-muted">{completedSteps}/{totalSteps} steps</span>
          </div>
          <div className="flex items-center gap-1.5 text-[11px] text-muted">
            {isStreaming && (
              <>
                <span className="h-1.5 w-1.5 rounded-full bg-[#FF5C00] animate-pulse" />
                <span>Processing</span>
              </>
            )}
            {isComplete && (
              <>
                <span className="h-1.5 w-1.5 rounded-full bg-[#FF5C00]" />
                <span className="text-[#FF5C00]">Complete</span>
              </>
            )}
            {isFailed && (
              <>
                <span className="h-1.5 w-1.5 rounded-full bg-danger" />
                <span className="text-danger">Failed</span>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Step dots */}
      <div className="mt-3 flex items-center gap-1">
        {Array.from({ length: totalSteps }).map((_, i) => (
          <div
            key={i}
            className={`h-1 flex-1 rounded-full transition-all duration-500 ${
              i < completedSteps
                ? "bg-[#FF5C00]"
                : i === completedSteps && isStreaming
                ? "bg-[#FF5C00] animate-pulse"
                : "bg-surface"
            }`}
          />
        ))}
      </div>
    </div>
  );
}
