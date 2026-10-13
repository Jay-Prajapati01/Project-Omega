"use client";

import { useRef, useEffect, useState, KeyboardEvent } from "react";
import { motion } from "framer-motion";
import { Search, Mic, Paperclip, Send, Command, Sparkles, Loader2 } from "lucide-react";

interface Props {
  query: string;
  setQuery: (q: string) => void;
  onSend: () => void;
  loading: boolean;
  placeholder?: string;
  compact?: boolean;
  onFile?: (file: File) => void;
  uploading?: boolean;
}

export function ChatInput({
  query,
  setQuery,
  onSend,
  loading,
  placeholder,
  compact,
  onFile,
  uploading,
}: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const recognitionRef = useRef<any>(null);
  const spokenBaseRef = useRef("");
  const [listening, setListening] = useState(false);
  // Detected after mount so server and client render the same markup.
  const [speechSupported, setSpeechSupported] = useState<boolean | null>(null);

  useEffect(() => {
    setSpeechSupported(
      Boolean(
        (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
      )
    );
  }, []);

  useEffect(() => {
    const handler = (e: globalThis.KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };
    document.addEventListener("keydown", handler);
    return () => {
      document.removeEventListener("keydown", handler);
      recognitionRef.current?.stop?.();
    };
  }, []);

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey && query.trim()) {
      e.preventDefault();
      onSend();
    }
  };

  const toggleVoice = () => {
    const SpeechRecognitionImpl =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognitionImpl) return;
    if (listening) {
      recognitionRef.current?.stop?.();
      return;
    }
    try {
      const rec = new SpeechRecognitionImpl();
      rec.lang = "en-US";
      rec.interimResults = true;
      rec.continuous = false;
      // Preserve anything already typed and append the transcript to it.
      spokenBaseRef.current = query.trim() ? `${query.trim()} ` : "";
      rec.onresult = (event: any) => {
        const transcript = Array.from(event.results as any[])
          .map((result: any) => result[0]?.transcript || "")
          .join(" ");
        setQuery(spokenBaseRef.current + transcript);
      };
      rec.onend = () => setListening(false);
      rec.onerror = () => setListening(false);
      recognitionRef.current = rec;
      rec.start();
      setListening(true);
    } catch {
      setListening(false);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file && onFile) onFile(file);
    e.target.value = "";
  };

  if (compact) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        className="relative"
      >
        <div className="group relative flex items-center rounded-[16px] border-2 border-ink bg-card transition-all duration-300 focus-within:border-[#FF5C00]/50 focus-within:shadow-[0_0_0_3px_rgba(255,92,0,0.12)]">
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder || "Ask a follow-up..."}
            className="h-12 flex-1 bg-transparent pl-5 pr-4 text-[13px] text-foreground placeholder:text-muted outline-none"
          />
          <button
            onClick={() => query.trim() && onSend()}
            disabled={!query.trim() || loading}
            className="mr-2 flex h-8 w-8 items-center justify-center rounded-[10px] bg-[#FF5C00] text-ink transition-all hover:bg-[#E14E00] disabled:opacity-30"
          >
            {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
          </button>
        </div>
      </motion.div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.1 }}
      className="relative"
    >
      <div className="group relative flex items-center rounded-[18px] border-2 border-ink bg-card transition-all duration-300 focus-within:border-[#FF5C00]/50 focus-within:shadow-[0_0_0_4px_rgba(255,92,0,0.12),0_0_40px_rgba(255,92,0,0.06)]">
        <div className="flex h-[64px] items-center pl-5">
          <Search className="h-5 w-5 text-muted transition-colors group-focus-within:text-[#FF5C00]" />
        </div>

        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={listening ? "Listening..." : placeholder || "Ask anything about your knowledge..."}
          size={1}
          className="h-[64px] min-w-0 flex-1 bg-transparent px-4 text-[15px] font-normal text-foreground placeholder:text-muted outline-none"
        />

        {query && (
          <button
            onClick={() => setQuery("")}
            className="mr-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-muted transition-colors hover:bg-surface hover:text-foreground"
          >
            <span className="text-[14px]">×</span>
          </button>
        )}

        <button
          type="button"
          onClick={toggleVoice}
          className={`mr-1 hidden h-9 w-9 shrink-0 items-center justify-center rounded-xl transition-colors hover:bg-surface sm:flex ${
            listening ? "text-[#FF5C00]" : "text-muted hover:text-foreground"
          }`}
          title={
            speechSupported === false
              ? "Voice input is not supported in this browser"
              : listening
                ? "Listening... (click to stop)"
                : "Voice input"
          }
          aria-label="Voice input"
          aria-pressed={listening}
        >
          <Mic className={`h-4 w-4 ${listening ? "animate-pulse" : ""}`} />
        </button>

        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading}
          className="mr-1 hidden h-9 w-9 shrink-0 items-center justify-center rounded-xl text-muted transition-colors hover:bg-surface hover:text-foreground disabled:opacity-50 sm:flex"
          title="Attach file"
          aria-label="Attach file"
        >
          {uploading ? (
            <Loader2 className="h-4 w-4 animate-spin text-[#FF5C00]" />
          ) : (
            <Paperclip className="h-4 w-4" />
          )}
        </button>
        <input
          ref={fileInputRef}
          type="file"
          className="hidden"
          accept=".pdf,.doc,.docx,.txt,.md,.epub,.mp3,.wav,.m4a,.aac,.flac,.ogg,.mp4,.webm"
          onChange={handleFileChange}
        />

        <button
          onClick={() => query.trim() && onSend()}
          disabled={!query.trim() || loading}
          className="mr-2 flex h-11 shrink-0 items-center gap-2 rounded-[14px] bg-[#FF5C00] border-2 border-ink px-3 text-[13px] font-semibold text-ink transition-all hover:bg-[#E14E00] disabled:opacity-40 disabled:cursor-not-allowed shadow-lg shadow-[#FF5C00]/20 sm:px-5"
          aria-label="Send message"
        >
          {loading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Sparkles className="h-4 w-4" />
          )}
          <span className="hidden sm:inline">Send</span>
        </button>

        <div className="mr-4 hidden shrink-0 items-center gap-1 rounded-md bg-surface px-2.5 py-1.5 sm:flex">
          <Command className="h-3 w-3 text-muted" />
          <span className="text-[11px] font-medium text-muted">K</span>
        </div>
      </div>
    </motion.div>
  );
}
