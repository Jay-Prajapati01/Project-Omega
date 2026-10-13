"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Youtube,
  Instagram,
  FileText,
  Files,
  Mic,
  Globe,
  ExternalLink,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { API_URL, SearchHit } from "@/lib/api";
import { ThumbImage } from "@/components/ThumbImage";

function getSourceIcon(type: string) {
  switch (type) {
    case "youtube": return <Youtube className="h-4 w-4" />;
    case "instagram": return <Instagram className="h-4 w-4" />;
    case "pdf": return <FileText className="h-4 w-4" />;
    case "document": return <Files className="h-4 w-4" />;
    case "audio": return <Mic className="h-4 w-4" />;
    case "web": return <Globe className="h-4 w-4" />;
    default: return <FileText className="h-4 w-4" />;
  }
}

function getSourceColor(type: string) {
  switch (type) {
    case "youtube": return "#FF5C00";
    case "instagram": return "#FF5C00";
    case "pdf": return "#E14E00";
    case "document": return "#E14E00";
    case "audio": return "#E14E00";
    case "web": return "#B96A00";
    default: return "#6B5B4D";
  }
}

function getSourceUrl(source: SearchHit): string | null {
  if (["pdf", "document", "audio"].includes(source.source_type)) return `/source/${encodeURIComponent(source.source_id)}`;
  if (source.url) {
    // Absolute API paths like "/api/sources/x/download" are valid;
    // anything else (channel names etc.) must NOT become a URL.
    if (source.url.startsWith("/")) {
      return `${API_URL}${source.url}`;
    }
    try {
      const u = new URL(source.url);
      if (u.protocol === "http:" || u.protocol === "https:") {
        return source.url;
      }
    } catch {
      // invalid URL
    }
  }
  return null;
}

function getActionLabel(type: string): string {
  switch (type) {
    case "youtube": return "Watch Video";
    case "instagram": return "View Post";
    case "pdf": return "Open PDF";
    case "document": return "Open Document";
    case "audio": return "Play Audio";
    case "web": return "Open Page";
    default: return "Open";
  }
}

interface Props {
  sources: SearchHit[];
  visibleCount?: number;
}

export function SourceReferenceCard({ sources, visibleCount = 5 }: Props) {
  const [expanded, setExpanded] = useState(false);
  const uniqueSources = Array.from(sources.reduce((grouped, source) => {
    const key = `${source.source_type}:${source.source_id}`;
    const previous = grouped.get(key);
    grouped.set(key, previous
      ? { ...previous, score: Math.max(previous.score, source.score), thumbnail: previous.thumbnail || source.thumbnail, url: previous.url || source.url }
      : source);
    return grouped;
  }, new Map<string, SearchHit>()).values());
  const visible = expanded ? uniqueSources : uniqueSources.slice(0, visibleCount);
  const hasMore = uniqueSources.length > visibleCount;

  if (uniqueSources.length === 0) return null;

  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-[12px] font-semibold uppercase tracking-wider text-muted">
          Sources
        </h3>
        {hasMore && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="flex items-center gap-1 text-[11px] text-[#FF5C00] hover:text-[#E14E00] transition-colors"
          >
            {expanded ? "Show less" : `View all ${uniqueSources.length} sources`}
            {expanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
        <AnimatePresence>
          {visible.map((source, i) => {
            const color = getSourceColor(source.source_type);
            const url = getSourceUrl(source);
            return (
              <motion.div
                key={`${source.source_type}:${source.source_id}`}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ delay: i * 0.05 }}
                whileHover={{ y: -2, scale: 1.01 }}
              >
                <div className="group relative overflow-hidden rounded-[14px] border-2 border-ink bg-surface p-3 transition-all duration-200 hover:border-brand/40">
                  <div className="flex gap-3">
                    {source.thumbnail ? (
                      <div className="relative h-16 w-24 flex-shrink-0 overflow-hidden rounded-[10px]">
                        <ThumbImage
                          src={source.thumbnail}
                          className="h-full w-full object-cover"
                          fallbackClassName="h-16 w-24"
                        />
                      </div>
                    ) : (
                      <div
                        className="flex h-16 w-16 flex-shrink-0 items-center justify-center rounded-[10px]"
                        style={{ backgroundColor: `${color}15` }}
                      >
                        <div style={{ color }}>{getSourceIcon(source.source_type)}</div>
                      </div>
                    )}

                    <div className="min-w-0 flex-1">
                      <div className="mb-1 flex items-center gap-1.5">
                        <span
                          className="rounded-full px-1.5 py-0.5 text-[9px] font-semibold capitalize"
                          style={{ backgroundColor: `${color}15`, color }}
                        >
                          {source.source_type}
                        </span>
                        <span className="text-[9px] font-semibold text-muted">{source.score >= 0.68 ? "Strong match" : source.score >= 0.5 ? "Good match" : "Related"}</span>
                      </div>
                      <div className="truncate text-[11px] font-medium text-foreground">
                        {source.title || source.source_id}
                      </div>
                    </div>
                  </div>
                  <div className="mt-3 flex items-center justify-between gap-2 border-t border-ink/10 pt-2">
                    <span className="text-[10px] text-muted">Relevance score <b className="text-foreground">{Math.round(source.score * 100)}/100</b></span>
                    {url && <a href={url} target={url.startsWith("http") ? "_blank" : "_self"} rel="noopener noreferrer" className="inline-flex items-center gap-1.5 rounded-lg border border-ink/20 bg-card px-2.5 py-1.5 text-[10px] font-bold text-foreground hover:bg-brand-soft">
                      {getActionLabel(source.source_type)} <ExternalLink className="h-3 w-3" />
                    </a>}
                  </div>
                </div>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>
    </div>
  );
}
