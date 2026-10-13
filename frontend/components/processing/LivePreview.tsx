"use client";

import { useEffect, useRef, useState, useMemo } from "react";
import { SSEEvent } from "@/hooks/useSSE";

interface LivePreviewProps {
  events: SSEEvent[];
  isStreaming: boolean;
  isIdle: boolean;
  sourceType: string;
}

const STAGE_LABELS: Record<string, Record<number, string>> = {
  youtube: { 2: "Fetching metadata...", 3: "Fetching transcript...", 4: "Generating summary...", 5: "Chunking content...", 6: "Creating embeddings...", 7: "Indexing..." },
  instagram: { 2: "Rendering page...", 3: "Extracting caption...", 4: "Downloading media...", 5: "Running OCR & Whisper...", 6: "Generating summary...", 7: "Indexing..." },
  pdf: { 2: "Detecting document type...", 3: "Parsing layout...", 4: "Running OCR...", 5: "Extracting tables...", 6: "Extracting images...", 7: "Detecting headings...", 8: "Creating structured content...", 9: "Cleaning document...", 10: "Semantic chunking...", 11: "Creating embeddings...", 12: "Generating summary...", 13: "Indexing to vector DB..." },
  document: { 2: "Extracting text...", 3: "Generating summary...", 4: "Chunking content...", 5: "Creating embeddings...", 6: "Indexing..." },
  audio: { 2: "Transcribing audio...", 3: "Generating summary...", 4: "Chunking content...", 5: "Creating embeddings...", 6: "Indexing..." },
  web: { 1: "Validating URL...", 2: "Fetching & extracting content...", 3: "Generating AI summary...", 4: "Creating embeddings...", 5: "Indexing to vector DB..." },
};

export function LivePreview({ events, isStreaming, isIdle, sourceType }: LivePreviewProps) {
  const [thumbnail, setThumbnail] = useState<string | null>(null);
  const [title, setTitle] = useState<string>("");
  const [channel, setChannel] = useState<string>("");
  const [duration, setDuration] = useState<number | null>(null);
  const [transcript, setTranscript] = useState<string>("");
  const [streamingText, setStreamingText] = useState<string>("");
  const [isStreamingSummary, setIsStreamingSummary] = useState(false);
  const [summary, setSummary] = useState<string>("");
  const [topics, setTopics] = useState<string[]>([]);
  const [previewChars, setPreviewChars] = useState<number | null>(null);
  const summaryRef = useRef<HTMLDivElement>(null);
  const processedIdx = useRef(0);

  useEffect(() => {
    const newEvents = events.slice(processedIdx.current);
    processedIdx.current = events.length;
    for (const evt of newEvents) {
      const d = evt.data;
      switch (evt.event) {
        case "step_complete":
          if (d.thumbnail) setThumbnail(d.thumbnail);
          if (d.title) setTitle(d.title);
          if (d.channel) setChannel(d.channel);
          if (d.duration) setDuration(d.duration);
          if (d.summary) { setSummary(d.summary); setIsStreamingSummary(false); }
          if (d.topics) setTopics(d.topics);
          if (d.chars) setPreviewChars(d.chars);
          break;
        case "preview":
          if (d.thumbnail) setThumbnail(d.thumbnail);
          if (d.title) setTitle(d.title);
          if (d.channel) setChannel(d.channel);
          if (d.text) setTranscript(d.text);
          if (d.chars) setPreviewChars(d.chars);
          break;
        case "stream_token":
          setIsStreamingSummary(true);
          setStreamingText((p) => p + (d.token || ""));
          break;
        case "complete":
          if (d.title) setTitle(d.title);
          if (d.summary) { setSummary(d.summary); setIsStreamingSummary(false); }
          if (d.key_topics) setTopics(d.key_topics);
          break;
      }
    }
  }, [events]);

  useEffect(() => {
    if (summaryRef.current) {
      summaryRef.current.scrollTop = summaryRef.current.scrollHeight;
    }
  }, [streamingText, summary]);

  const isComplete = events.some((e) => e.event === "complete");
  const hasFailed = events.some((e) => e.event === "step_fail");

  const currentStage = useMemo(() => {
    if (isComplete) return "done";
    if (hasFailed) return "failed";
    const labels = STAGE_LABELS[sourceType] || STAGE_LABELS.web;
    for (let i = events.length - 1; i >= 0; i--) {
      if (events[i].event === "step_start") {
        const step = events[i].data.step;
        return labels[step] || events[i].data.description || "Processing...";
      }
    }
    if (isStreaming) return "connecting";
    return "waiting";
  }, [events, sourceType, isComplete, hasFailed, isStreaming]);

  const displaySummary = summary || streamingText;
  const isVideo = sourceType === "youtube" || sourceType === "instagram";

  if (isIdle) {
    return (
      <div className="flex h-full min-h-[400px] items-center justify-center rounded-[20px] border-2 border-ink bg-card">
        <div className="text-center">
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-surface">
            <span className="text-xl">👁️</span>
          </div>
          <p className="text-[13px] font-medium text-foreground-3">Live Preview</p>
          <p className="mt-1 text-[11px] text-muted">Content appears here during processing</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 rounded-[12px] border-2 border-ink bg-card px-3 py-2">
        <span className={`h-1.5 w-1.5 rounded-full ${isComplete ? "bg-[#FF5C00]" : hasFailed ? "bg-danger" : "bg-[#FF5C00] animate-pulse"}`} />
        <span className="text-[11px] font-medium text-foreground-3">
          {currentStage === "waiting" ? "Initializing..." :
           currentStage === "connecting" ? "Connecting..." :
           currentStage === "done" ? "Complete" :
           currentStage === "failed" ? "Failed" :
           currentStage}
        </span>
      </div>

      {thumbnail && (
        <div className="animate-fade-in overflow-hidden rounded-[20px] border-2 border-ink bg-card">
          <div className="relative">
            <img src={thumbnail} alt={title} className="h-40 w-full object-cover" />
            <div className="absolute inset-0 bg-gradient-to-t from-card via-transparent to-transparent" />
            {duration && (
              <span className="absolute bottom-2 right-2 rounded-[8px] bg-black/70 px-2 py-0.5 text-[10px] tabular-nums font-semibold text-paper">
                {Math.floor(duration / 60)}:{(duration % 60).toString().padStart(2, "0")}
              </span>
            )}
          </div>
          <div className="p-3.5">
            <h3 className="text-[13px] font-semibold text-foreground line-clamp-2 leading-tight">{title}</h3>
            {channel && <p className="mt-1 text-[11px] text-muted">{channel}</p>}
          </div>
        </div>
      )}

      {!thumbnail && title && (
        <div className="animate-fade-in rounded-[20px] border-2 border-ink bg-card p-3.5">
          <h3 className="text-[13px] font-semibold text-foreground line-clamp-2 leading-tight">{title}</h3>
          {previewChars != null && previewChars > 0 && <p className="mt-1 text-[11px] text-muted">{previewChars.toLocaleString()} characters extracted</p>}
        </div>
      )}

      {transcript && (
        <div className="animate-fade-in rounded-[20px] border-2 border-ink bg-card p-3.5">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-[10px] font-bold uppercase tracking-wider text-muted">
              {isVideo ? "Transcript" : "Extracted Content"}
            </span>
            <span className="text-[10px] tabular-nums text-muted">{transcript.length.toLocaleString()} chars</span>
          </div>
          <div className="max-h-36 overflow-y-auto rounded-[10px] bg-surface p-3">
            <p className="text-[11px] leading-relaxed text-foreground-3 whitespace-pre-wrap">{transcript}</p>
          </div>
        </div>
      )}

      {displaySummary && (
        <div className="animate-fade-in rounded-[20px] border-2 border-ink bg-card p-3.5">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-[10px] font-bold uppercase tracking-wider text-muted">AI Summary</span>
            {isStreamingSummary && (
              <span className="inline-flex items-center gap-1 text-[10px] text-[#FF5C00]">
                <span className="h-1 w-1 rounded-full bg-[#FF5C00] animate-pulse" />
                Streaming
              </span>
            )}
          </div>
          <div ref={summaryRef} className="max-h-48 overflow-y-auto rounded-[10px] bg-surface p-3">
            <p className={`text-[12px] leading-relaxed text-foreground-3 whitespace-pre-wrap ${isStreamingSummary ? "streaming-cursor" : ""}`}>
              {displaySummary}
            </p>
          </div>
        </div>
      )}

      {topics.length > 0 && (
        <div className="animate-fade-in rounded-[20px] border-2 border-ink bg-card p-3.5">
          <span className="text-[10px] font-bold uppercase tracking-wider text-muted">Key Topics</span>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {topics.map((t) => (
              <span key={t} className="rounded-full bg-[#FF5C00]/10 px-2.5 py-1 text-[10px] font-medium text-[#FF5C00]">{t}</span>
            ))}
          </div>
        </div>
      )}

      {!thumbnail && !title && !transcript && !displaySummary && isStreaming && (
        <div className="flex h-48 items-center justify-center rounded-[20px] border-2 border-ink bg-card">
          <div className="text-center">
            <div className="mx-auto mb-2 h-5 w-5 rounded-full border-2 border-[#FF5C00] border-t-transparent animate-spin" />
            <p className="text-[11px] text-muted">
              {currentStage === "connecting" ? "Connecting to server..." : "Waiting for content..."}
            </p>
          </div>
        </div>
      )}

      {isComplete && !thumbnail && !transcript && !displaySummary && (
        <div className="flex h-48 items-center justify-center rounded-[20px] border-2 border-ink bg-card">
          <div className="text-center">
            <div className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-[#FF5C00]/20">
              <svg className="h-5 w-5 text-[#FF5C00]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <p className="text-[12px] font-medium text-foreground-3">Content processed</p>
            <p className="mt-1 text-[11px] text-muted">Indexed and ready for search</p>
          </div>
        </div>
      )}

      {hasFailed && (thumbnail || transcript || displaySummary) && (
        <div className="flex items-start gap-2.5 rounded-[12px] border border-danger/30 bg-danger/10 px-3 py-2.5">
          <svg className="mt-0.5 h-3.5 w-3.5 shrink-0 text-danger" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
          </svg>
          <div className="text-[11px] leading-relaxed text-[#FCA5A5]">
            Processing failed partway through — what was extracted so far is shown, but this source may be incomplete.
          </div>
        </div>
      )}

      {hasFailed && !thumbnail && !transcript && !displaySummary && (
        <div className="flex h-48 items-center justify-center rounded-[20px] border-2 border-ink bg-card">
          <div className="text-center">
            <div className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-danger/20">
              <svg className="h-5 w-5 text-danger" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </div>
            <p className="text-[12px] font-medium text-foreground-3">Processing failed</p>
            <p className="mt-1 text-[11px] text-muted">Check error details below</p>
          </div>
        </div>
      )}
    </div>
  );
}
