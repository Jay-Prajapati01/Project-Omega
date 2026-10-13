"use client";

import { useMemo } from "react";
import { SSEEvent } from "@/hooks/useSSE";
import { MessageSquare } from "lucide-react";

interface AskAIContext {
  sourceId: string;
  title: string;
  summary: string;
}

interface ResultSectionProps {
  events: SSEEvent[];
  isStreaming: boolean;
  onAskAI?: (ctx: AskAIContext) => void;
}

export function ResultSection({ events, isStreaming, onAskAI }: ResultSectionProps) {
  const completeEvent = useMemo(() => events.find((e) => e.event === "complete"), [events]);
  const data = completeEvent?.data;

  const totalMs = useMemo(() => {
    // `duration_ms` is CUMULATIVE time since the pipeline started (ms() in the
    // SSE endpoints), so the total is the last/largest value — summing them
    // would count the same elapsed time once per step.
    let ms = 0;
    for (const e of events) {
      if (e.event === "step_complete" && typeof e.data.duration_ms === "number") {
        ms = Math.max(ms, e.data.duration_ms);
      }
    }
    return ms;
  }, [events]);

  const sourceId = data?.source_id || data?.video_id || data?.post_id || "";
  const title = data?.title || "";
  const summary = data?.summary || "";

  if (isStreaming || !completeEvent || !data) return null;

  return (
    <div className="animate-slide-up space-y-4">
      {/* Completion banner */}
      <div className="flex items-center justify-between rounded-[20px] border border-[#FF5C00]/20 bg-[#FF5C00]/[0.04] p-4">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[#FF5C00]/20">
            <svg className="h-4 w-4 text-[#FF5C00]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <div>
            <p className="text-[13px] font-semibold text-foreground">
              All steps completed in {(totalMs / 1000).toFixed(1)}s
            </p>
            <p className="text-[11px] text-muted">Content has been successfully processed and indexed.</p>
          </div>
        </div>
      </div>

      {/* Result cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="rounded-[16px] border-2 border-ink bg-card p-3.5">
          <div className="mb-2 flex items-center gap-1.5">
            <span className="text-[11px]">📝</span>
            <span className="text-[9px] font-bold uppercase tracking-wider text-muted">Summary</span>
          </div>
          <p className="text-[11px] leading-relaxed text-foreground-3 line-clamp-4">{summary || "—"}</p>
        </div>
        <div className="rounded-[16px] border-2 border-ink bg-card p-3.5">
          <div className="mb-2 flex items-center gap-1.5">
            <span className="text-[11px]">🏷️</span>
            <span className="text-[9px] font-bold uppercase tracking-wider text-muted">Topics</span>
          </div>
          <div className="flex flex-wrap gap-1">
            {(data.key_topics || []).slice(0, 5).map((t: string) => (
              <span key={t} className="rounded-full bg-[#FF5C00]/10 px-2 py-0.5 text-[9px] font-medium text-[#FF5C00]">{t}</span>
            ))}
          </div>
        </div>
        <div className="rounded-[16px] border-2 border-ink bg-card p-3.5">
          <div className="mb-2 flex items-center gap-1.5">
            <span className="text-[11px]">🕸️</span>
            <span className="text-[9px] font-bold uppercase tracking-wider text-muted">Knowledge</span>
          </div>
          <div className="space-y-1 text-[11px] text-foreground-3">
            <p>Graph updated</p>
            <p className="text-[10px] text-muted">Relationships extracted</p>
          </div>
        </div>
        <div className="rounded-[16px] border-2 border-ink bg-card p-3.5">
          <div className="mb-2 flex items-center gap-1.5">
            <span className="text-[11px]">📊</span>
            <span className="text-[9px] font-bold uppercase tracking-wider text-muted">Stats</span>
          </div>
          <div className="space-y-1">
            <div className="flex justify-between text-[11px]">
              <span className="text-muted">Chunks</span>
              <span className="tabular-nums font-medium text-foreground-3">{data.chunks_indexed || 0}</span>
            </div>
            <div className="flex justify-between text-[11px]">
              <span className="text-muted">Vectors</span>
              <span className="tabular-nums font-medium text-foreground-3">{data.chunks_indexed || 0}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Ask AI */}
      {onAskAI && sourceId && (
        <button
          onClick={() => onAskAI({ sourceId, title, summary })}
          className="w-full rounded-[16px] border border-[#FF5C00]/20 bg-[#FF5C00]/[0.06] p-3.5 text-[13px] font-medium text-[#FF5C00] transition-all hover:bg-[#FF5C00]/[0.12] hover:border-[#FF5C00]/30 hover:shadow-[0_0_20px_rgba(255,92,0,0.1)] flex items-center justify-center gap-2"
        >
          <MessageSquare className="h-4 w-4" />
          Ask AI about this content
          <span className="text-[#FF5C00]/60">→</span>
        </button>
      )}
    </div>
  );
}
