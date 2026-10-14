"use client";

import { useState, useCallback, useEffect, useRef, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Sparkles, HelpCircle, Loader2, CheckCircle2, AlertCircle } from "lucide-react";
import {
  api,
  askChat,
  ChatResponse,
  ChatMessage,
  getStats,
  processPdf,
  processDocument,
  processAudio,
  runChatAction,
} from "@/lib/api";
import { useAppStore } from "@/lib/store";
import { useToast } from "@/components/ui";
import {
  ChatInput,
  SourceFilterChips,
  AnswerCard,
  FollowUpInput,
  ChatEmptyState,
  ChatLoadingState,
  ChatErrorState,
  SourceReferenceCard,
} from "@/components/chat";
import type { FollowUpAction } from "@/components/chat/FollowUpInput";

type UploadStatus =
  | { status: "uploading" | "done" | "error"; name: string; message?: string };

const AUDIO_EXTENSIONS = ["mp3", "wav", "m4a", "aac", "flac", "ogg", "mp4", "webm"];

export default function ChatPage() {
  // useSearchParams() requires a Suspense boundary for `next build`
  return (
    <Suspense fallback={null}>
      <ChatPageInner />
    </Suspense>
  );
}

function ChatPageInner() {
  const searchParams = useSearchParams();
  const sourceParam = searchParams.get("source") || "";
  const sourceIdParam = searchParams.get("sourceId") || "";
  const titleParam = searchParams.get("title") || "";
  const summaryParam = searchParams.get("summary") || "";
  const qParam = searchParams.get("q") || "";

  const lastAutoQuery = useRef<string | null>(null);

  const [query, setQuery] = useState(() => {
    if (qParam) return qParam;
    if (titleParam) {
      return `Tell me about "${titleParam}"`;
    }
    return "";
  });
  const [filter, setFilter] = useState(sourceParam);
  const [sourceId, setSourceId] = useState(sourceIdParam);
  const [conversationId, setConversationId] = useState<string | undefined>();
  const [history, setHistory] = useState<ChatResponse[]>([]);
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [pendingQuestion, setPendingQuestion] = useState("");
  const [actionPending, setActionPending] = useState(false);
  const [upload, setUpload] = useState<UploadStatus | null>(null);
  const addQuestion = useAppStore((s) => s.addQuestion);
  const addSearch = useAppStore((s) => s.addSearch);
  const queryClient = useQueryClient();
  const { notify } = useToast();

  const { data: stats } = useQuery({
    queryKey: ["stats"],
    queryFn: getStats,
  });

  useEffect(() => {
    const id = sessionStorage.getItem("mindmesh-chat-id");
    if (!id || sourceIdParam || qParam) return;
    api.get(`/chat/conversations/${encodeURIComponent(id)}`).then(({ data }) => {
      setConversationId(id);
      const responses: ChatResponse[] = data.turns.map((t: { response: ChatResponse }) => t.response);
      setHistory(responses);
      setChatHistory(responses.flatMap(r => [{ role: "user" as const, content: r.question }, { role: "assistant" as const, content: r.answer }]));
    }).catch(() => sessionStorage.removeItem("mindmesh-chat-id"));
  }, [sourceIdParam, qParam]);

  const mutation = useMutation({
    mutationFn: (q: string) =>
      askChat(q, filter || undefined, sourceId || undefined, chatHistory, undefined, conversationId),
    onMutate: (q) => {
      setPendingQuestion(q);
    },
    onSuccess: (data) => {
      if (data.conversation_id) {
        setConversationId(data.conversation_id);
        sessionStorage.setItem("mindmesh-chat-id", data.conversation_id);
      }
      setHistory((h) => [...h, data]);
      setChatHistory((h) => [
        ...h,
        { role: "user", content: data.question },
        { role: "assistant", content: data.answer },
      ]);
      addQuestion(data.question);
      addSearch(data.question);
      queryClient.invalidateQueries({ queryKey: ["stats"] });
      setError(null);
    },
    onSettled: () => setPendingQuestion(""),
    onError: (err: any, failedQuestion) => {
      const detail = err?.response?.data?.detail;
      setError(typeof detail === "string" ? detail : detail?.message || err?.message || "Failed to generate answer. Is the backend running?");
      // Restore the question so the user's input is not lost on failure.
      if (typeof failedQuestion === "string" && failedQuestion.trim()) {
        setQuery(failedQuestion);
      }
    },
  });

  const handleSend = useCallback(
    async (q: string) => {
      if (!q.trim()) return;
      setQuery("");
      setError(null);
      try {
        const { data } = await api.get<{ enabled: boolean; used: number | null; limit: number | null }>("/chat/quota");
        if (data.enabled && data.used !== null && data.limit) {
          const percent = (data.used / data.limit) * 100;
          if (percent >= 90) notify("You’re close to your daily AI request limit. This request may use the remaining quota.", "info");
          else if (percent >= 80) notify("You’re approaching your daily AI request limit. Save your work and avoid repeated requests.", "info");
        }
      } catch { /* Preflight is advisory. The server enforces the quota on submission. */ }
      mutation.mutate(q);
    },
    [mutation, notify]
  );

  const handleDirectSend = useCallback(() => {
    if (query.trim()) {
      handleSend(query);
    }
  }, [query, handleSend]);

  const handleQuickAction = useCallback(async (action: FollowUpAction) => {
    const previous = history[history.length - 1];
    if (!previous) return;
    const prompts: Record<FollowUpAction, string> = {
      explain: "Explain more",
      notes: "Create Notes",
      flashcards: "Generate Flashcards",
      export: "Export Markdown",
      compare: "Compare Sources",
      simplify: "Simplify",
    };
    const actionQuestion = prompts[action];

    const appendLocalReply = (question: string, answer: string) => {
      const response: ChatResponse = {
        question,
        answer,
        citations: action === "compare" ? [] : previous.citations,
        related_sources: previous.related_sources || [],
      };
      setHistory((items) => [...items, response]);
      setChatHistory((items) => [
        ...items,
        { role: "user", content: question },
        { role: "assistant", content: answer },
      ]);
    };

    if (action === "export") {
      try {
        const sources = (previous.related_sources || []).map((source) =>
          `- **${source.title || source.source_id}** (${source.source_type}) — relevance ${Math.round(source.score * 100)}/100`,
        );
        const markdown = [
          `# ${previous.question}`,
          "",
          previous.answer.replace(/\[(?:source\s*)?\d+\]/gi, "").trim(),
          "",
          "## Sources",
          "",
          ...(sources.length ? sources : ["No matched sources were attached to this answer."]),
          "",
        ].join("\n");
        const blobUrl = URL.createObjectURL(new Blob([markdown], { type: "text/markdown;charset=utf-8" }));
        const anchor = document.createElement("a");
        anchor.href = blobUrl;
        anchor.download = `mindmesh-answer-${new Date().toISOString().slice(0, 10)}.md`;
        document.body.appendChild(anchor);
        anchor.click();
        anchor.remove();
        window.setTimeout(() => URL.revokeObjectURL(blobUrl), 1000);
        notify("Markdown export downloaded with the answer and its matched sources.", "success");
      } catch {
        notify("Markdown export could not be created in this browser. Please try again.", "error");
      }
      return;
    }

    const related = previous.related_sources || [];
    const sourceIds = Array.from(new Set(related.map((source) => source.source_id).filter(Boolean)));
    if (action === "compare" && sourceIds.length < 2) {
      appendLocalReply(
        actionQuestion,
        `I can compare sources when this answer has at least two distinct saved items. I found ${sourceIds.length}; try a broader question that matches more of your saved content, or save another related source.`,
      );
      return;
    }

    setActionPending(true);
    setPendingQuestion(actionQuestion);
    setError(null);
    try {
      const response = await runChatAction({
        action,
        question: `${actionQuestion}: ${previous.question}`,
        answer: previous.answer,
        conversation_id: conversationId,
        source_ids: sourceIds.slice(0, 8),
        citations: previous.citations,
        related_sources: related.slice(0, 12),
      });
      if (response.conversation_id) {
        setConversationId(response.conversation_id);
        sessionStorage.setItem("mindmesh-chat-id", response.conversation_id);
      }
      setHistory((items) => [...items, response]);
      setChatHistory((items) => [
        ...items,
        { role: "user", content: response.question },
        { role: "assistant", content: response.answer },
      ]);
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      const reason = typeof detail === "string"
        ? detail
        : detail?.message || `The ${actionQuestion.toLowerCase()} action could not finish because the AI or source service is unavailable. Your saved sources were not changed; please try again shortly.`;
      appendLocalReply(actionQuestion, reason);
      notify(reason, "error");
    } finally {
      setActionPending(false);
      setPendingQuestion("");
    }
  }, [conversationId, history, notify]);

  const handleFile = useCallback(
    async (file: File) => {
      setUpload({ status: "uploading", name: file.name });
      try {
        const ext = file.name.split(".").pop()?.toLowerCase() || "";
        if (ext === "pdf") {
          await processPdf(file);
        } else if (AUDIO_EXTENSIONS.includes(ext)) {
          await processAudio(file);
        } else {
          await processDocument(file);
        }
        setUpload({ status: "done", name: file.name });
        queryClient.invalidateQueries({ queryKey: ["stats"] });
        queryClient.invalidateQueries({ queryKey: ["sources"] });
        setTimeout(() => setUpload(null), 4000);
      } catch (err: any) {
        setUpload({
          status: "error",
          name: file.name,
          message:
            err?.response?.data?.detail || err?.message || "Upload failed. Please try again.",
        });
        setTimeout(() => setUpload(null), 8000);
      }
    },
    [queryClient]
  );

  // Auto-send query links from the old Search entry and source-context links.
  useEffect(() => {
    const linkedQuery = qParam || (titleParam ? `Tell me about "${titleParam}"` : "");
    if (linkedQuery && lastAutoQuery.current !== linkedQuery) {
      lastAutoQuery.current = linkedQuery;
      setQuery(linkedQuery);
      const timer = setTimeout(() => mutation.mutate(linkedQuery), 300);
      return () => clearTimeout(timer);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [titleParam, qParam]);

  const handleClearHistory = useCallback(() => {
    setHistory([]);
    setChatHistory([]);
    setConversationId(undefined);
    sessionStorage.removeItem("mindmesh-chat-id");
  }, []);

  const isLoading = mutation.isPending || actionPending;
  const hasHistory = history.length > 0;
  const lastResponse = history[history.length - 1];

  return (
    <div className="min-h-screen">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="mb-6 flex flex-wrap items-start justify-between gap-4"
      >
        <div className="min-w-0">
          <div className="flex items-center gap-3">
            <h1 className="text-[24px] font-bold text-foreground tracking-tight">
              Ask AI
            </h1>
            <Sparkles className="h-5 w-5 text-[#FF5C00]" />
          </div>
          <p className="mt-1 text-[13px] text-muted">
            Chat with everything you&apos;ve indexed.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1 rounded-md bg-surface px-2.5 py-1.5">
            <Sparkles className="h-3 w-3 text-muted" />
            <span className="text-[11px] font-medium text-muted">⌘K</span>
          </div>
          {hasHistory && (
            <button
              onClick={handleClearHistory}
              className="flex items-center gap-2 rounded-[12px] border-2 border-ink bg-card px-4 py-2.5 text-[12px] font-medium text-foreground-3 transition-all hover:bg-surface hover:text-foreground"
            >
              New Chat
            </button>
          )}
          <button className="flex items-center gap-2 rounded-[12px] border-2 border-ink bg-card px-4 py-2.5 text-[12px] font-medium text-foreground-3 transition-all hover:bg-surface hover:text-foreground">
            <HelpCircle className="h-4 w-4" />
            Ask Tips
          </button>
        </div>
      </motion.div>

      {/* Source Filters */}
      <div className="mb-5">
        <SourceFilterChips
          filter={filter}
          setFilter={(f) => setFilter(f)}
          stats={stats?.sources_by_type}
        />
      </div>

      {/* Search Input */}
      <div className="mb-6">
        <ChatInput
          query={query}
          setQuery={setQuery}
          onSend={handleDirectSend}
          loading={isLoading}
          onFile={handleFile}
          uploading={upload?.status === "uploading"}
        />
        {upload && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-2 flex items-center gap-2 text-[12px]"
          >
            {upload.status === "uploading" && (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin text-[#FF5C00]" />
                <span className="text-muted">
                  Uploading &amp; indexing <span className="text-foreground">{upload.name}</span>…
                </span>
              </>
            )}
            {upload.status === "done" && (
              <>
                <CheckCircle2 className="h-3.5 w-3.5 text-[#FF5C00]" />
                <span className="text-foreground">
                  {upload.name} indexed — ask about it now.
                </span>
              </>
            )}
            {upload.status === "error" && (
              <>
                <AlertCircle className="h-3.5 w-3.5 text-red-500" />
                <span className="text-red-500">
                  {upload.name}: {upload.message}
                </span>
              </>
            )}
          </motion.div>
        )}
      </div>

      {/* Conversation */}
      <div className="space-y-6">
        {/* Keep completed turns mounted while the next answer is being generated. */}
        {hasHistory && (
          <div className="space-y-6">
            {history.map((item, i) => (
              <div key={i} className="space-y-4">
                {/* User Question */}
                <motion.div
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="flex justify-end"
                >
                  <div className="max-w-[80%] rounded-[16px] rounded-br-[4px] bg-[#FF5C00]/15 px-5 py-3 text-[13px] text-foreground">
                    {item.question}
                  </div>
                </motion.div>

                {/* AI Answer */}
                <AnswerCard response={item} index={i} />

                {/* Ranked source matches stay with the answer and open the original source directly. */}
                <div className="ml-11">
                  <SourceReferenceCard sources={item.related_sources || []} visibleCount={6} />
                </div>

                {/* Follow-up Input (only after last response) */}
                {i === history.length - 1 && !isLoading && !error && (
                  <FollowUpInput
                    onSend={handleSend}
                    onAction={handleQuickAction}
                    loading={isLoading}
                  />
                )}
              </div>
            ))}
          </div>
        )}

        {isLoading && (
          <motion.div
            key="pending-turn"
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            className="space-y-4"
            aria-live="polite"
          >
            {pendingQuestion && (
              <div className="flex justify-end">
                <div className="max-w-[80%] rounded-[16px] rounded-br-[4px] bg-[#FF5C00]/15 px-5 py-3 text-[13px] text-foreground">
                  {pendingQuestion}
                </div>
              </div>
            )}
            <ChatLoadingState />
          </motion.div>
        )}

        {!isLoading && error && (
          <ChatErrorState
            error={error}
            onRetry={() => {
              setError(null);
              const retryQuestion = query.trim() || pendingQuestion || history[history.length - 1]?.question;
              if (retryQuestion) mutation.mutate(retryQuestion);
            }}
            onBroaden={() => {
              setFilter("");
              setError(null);
              const retryQuestion = query.trim() || pendingQuestion || history[history.length - 1]?.question;
              if (retryQuestion) mutation.mutate(retryQuestion);
            }}
          />
        )}

        {!isLoading && !hasHistory && !error && (
          <ChatEmptyState onQuestionClick={handleSend} />
        )}
      </div>
    </div>
  );
}
