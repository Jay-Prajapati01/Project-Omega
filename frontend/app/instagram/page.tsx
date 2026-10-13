"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useSSE } from "@/hooks/useSSE";
import { API_URL } from "@/lib/api";
import { ProcessingHeader, PipelineTimeline, LivePreview, AnalyticsPanel, ResultSection } from "@/components/processing";
import { Search, X, Camera, Loader2 } from "lucide-react";

const INSTAGRAM_STEPS = [
  { id: "validate", name: "1. Validating URL", icon: "link", description: "Checking if the Instagram URL is valid...", weight: 2 },
  { id: "render", name: "2. Rendering Page", icon: "globe", description: "Opening post in headless browser via Playwright...", weight: 35 },
  { id: "caption", name: "3. Extracting Caption", icon: "document", description: "Parsing caption and username from page...", weight: 5 },
  { id: "media", name: "4. Extracting Media", icon: "scan", description: "Downloading images/video for processing...", weight: 10 },
  { id: "text", name: "5. Extracting Text", icon: "search", description: "Running OCR on images and Whisper on audio...", weight: 15 },
  { id: "summary", name: "6. Generating Summary", icon: "brain", description: "AI summarizing content using Ollama...", weight: 25 },
  { id: "indexing", name: "7. Indexing to Vector DB", icon: "database", description: "Creating embeddings and storing in Qdrant...", weight: 8 },
];

export default function InstagramPage() {
  const router = useRouter();
  const [url, setUrl] = useState("");
  const { events, isStreaming, error, result, startStream, cancel, startedAt } = useSSE("instagram");

  const isIdle = !isStreaming && events.length === 0 && !error;

  const handleProcess = () => {
    if (!url) return;
    startStream(`${API_URL}/api/instagram/process/stream`, { url });
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && url && !isStreaming) handleProcess();
  };

  let completedSteps = 0, activeStep = 0, failedStep = 0, activeStepName = "";
  const hasComplete = events.some((e) => e.event === "complete");
  for (const evt of events) {
    if (evt.event === "step_complete") completedSteps++;
    if (evt.event === "step_start") { activeStep = evt.data.step || 0; activeStepName = INSTAGRAM_STEPS[(evt.data.step || 1) - 1]?.name || ""; }
    if (evt.event === "step_fail") failedStep = evt.data.step || 0;
  }
  if (hasComplete) completedSteps = INSTAGRAM_STEPS.length;

  const overallProgress = (() => {
    if (events.some((e) => e.event === "complete")) return 100;
    let total = 0, done = 0;
    for (let i = 0; i < INSTAGRAM_STEPS.length; i++) {
      total += INSTAGRAM_STEPS[i].weight;
      const stepNum = i + 1;
      const lastEvt = [...events].reverse().find((e) => e.data?.step === stepNum);
      if (lastEvt?.event === "step_complete") done += INSTAGRAM_STEPS[i].weight;
      else if (lastEvt?.event === "step_progress" && lastEvt.data.progress) done += (INSTAGRAM_STEPS[i].weight * lastEvt.data.progress) / 100;
    }
    return total > 0 ? Math.round((done / total) * 100) : 0;
  })();

  return (
    <div className="min-h-screen">
      {/* Hero Section */}
      <div className="mb-6 rounded-[24px] border-2 border-ink bg-gradient-to-br from-card via-card to-brand-soft p-5 sm:mb-8 sm:p-8">
        <div className="flex items-start gap-5">
          <div className="flex h-16 w-16 flex-shrink-0 items-center justify-center rounded-[20px] bg-brand-soft shadow-brut">
            <Camera className="h-7 w-7 text-brand" />
          </div>
          <div className="flex-1">
            <h1 className="text-[28px] font-bold text-foreground tracking-tight">Instagram Intelligence</h1>
            <p className="mt-2 text-[15px] text-foreground-3 leading-relaxed max-w-2xl">
              Extract insights from Reels, Posts, and Stories. OCR text from images, transcribe audio, and build searchable knowledge.
            </p>
            <div className="mt-4 flex flex-wrap items-center gap-3">
              <span className="inline-flex items-center gap-1.5 rounded-full bg-brand-soft px-3 py-1.5 text-[11px] font-medium text-brand">
                <span className="h-1.5 w-1.5 rounded-full bg-[#FF5C00]" />
                Instagram
              </span>
              <span className="inline-flex items-center gap-1.5 rounded-full bg-surface px-3 py-1.5 text-[11px] font-medium text-muted">
                Playwright Browser
              </span>
              <span className="inline-flex items-center gap-1.5 rounded-full bg-surface px-3 py-1.5 text-[11px] font-medium text-muted">
                OCR + Whisper
              </span>
              <span className="inline-flex items-center gap-1.5 rounded-full bg-surface px-3 py-1.5 text-[11px] font-medium text-muted">
                No Login Required
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Input Section */}
      <div className="mb-6 rounded-[20px] border-2 border-ink bg-card p-5">
        <label className="mb-3 block text-[11px] font-bold uppercase tracking-wider text-muted">Post or Reel URL</label>
        <div className="flex gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
            <input
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="https://instagram.com/reel/..."
              disabled={isStreaming}
              className="w-full rounded-[14px] border-2 border-ink bg-surface py-3.5 pl-11 pr-11 text-[14px] text-foreground placeholder:text-muted outline-none transition-all focus:border-[#FF5C00]/50 focus:ring-2 focus:ring-[#FF5C00]/10 disabled:opacity-50"
            />
            {url && !isStreaming && (
              <button onClick={() => setUrl("")} className="absolute right-4 top-1/2 -translate-y-1/2 text-muted hover:text-foreground transition-colors">
                <X className="h-4 w-4" />
              </button>
            )}
          </div>
          {isStreaming ? (
            <button
              onClick={cancel}
              className="flex items-center gap-2 brut-btn bg-danger px-6 py-3.5 text-[13px] font-bold text-card transition-all"
            >
              <Loader2 className="h-4 w-4 animate-spin" />
              Cancel
            </button>
          ) : (
            <button
              onClick={handleProcess}
              disabled={!url}
              className="flex items-center gap-2 brut-btn bg-brand px-6 py-3.5 text-[13px] font-bold text-ink transition-all hover:bg-brand-hover disabled:cursor-not-allowed"
            >
              <Camera className="h-4 w-4" />
              Process Post
            </button>
          )}
        </div>
        <p className="mt-3 text-[12px] text-muted">
          Works with public posts, Reels, and carousel images. No login required. Playwright renders the page to extract content.
        </p>
      </div>

      {/* Processing header */}
      {!isIdle && (
        <div className="mb-6">
          <ProcessingHeader
            sourceType="instagram"
            title={result?.title || url}
            startedAt={startedAt}
            totalSteps={INSTAGRAM_STEPS.length}
            completedSteps={completedSteps}
            activeStep={activeStep}
            activeStepName={activeStepName}
            failedStep={failedStep}
            isStreaming={isStreaming}
            onCancel={cancel}
            overallProgress={overallProgress}
          />
        </div>
      )}

      {/* Three-column layout */}
      <div className="grid grid-cols-12 gap-5">
        <div className="col-span-12 lg:col-span-5">
          <div className="rounded-[20px] border-2 border-ink bg-card p-5">
            <div className="mb-4 flex items-center justify-between">
              <span className="text-[11px] font-bold uppercase tracking-wider text-muted">Pipeline Progress</span>
              {!isIdle && <span className="rounded-full bg-brand-soft px-2.5 py-1 text-[10px] font-semibold tabular-nums text-brand">{completedSteps}/{INSTAGRAM_STEPS.length}</span>}
            </div>
            <PipelineTimeline steps={INSTAGRAM_STEPS} events={events} isStreaming={isStreaming} error={error} isIdle={isIdle} />
          </div>
        </div>
        <div className="col-span-12 lg:col-span-4">
          <LivePreview events={events} isStreaming={isStreaming} isIdle={isIdle} sourceType="instagram" />
        </div>
        <div className="col-span-12 lg:col-span-3">
          <AnalyticsPanel events={events} steps={INSTAGRAM_STEPS} isStreaming={isStreaming} isIdle={isIdle} startedAt={startedAt} />
        </div>
      </div>

      {error && !isStreaming && (
        <div className="mt-6 rounded-[20px] border border-danger/30 bg-danger/5 p-5">
          <div className="flex items-start gap-3">
            <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-danger/10">
              <X className="h-4 w-4 text-danger" />
            </div>
            <div>
              <p className="text-[13px] font-medium text-danger">Processing Error</p>
              <p className="mt-1 text-[12px] text-muted">{error}</p>
            </div>
          </div>
        </div>
      )}
      <div className="mt-6">
        <ResultSection
          events={events}
          isStreaming={isStreaming}
          onAskAI={(ctx) => {
            const params = new URLSearchParams({ source: "instagram", sourceId: ctx.sourceId, title: ctx.title, summary: ctx.summary });
            router.push(`/chat?${params.toString()}`);
          }}
        />
      </div>
    </div>
  );
}
