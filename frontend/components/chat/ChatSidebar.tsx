"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import {
  Layers,
  Database,
  Network,
  Clock,
  HelpCircle,
  ArrowRight,
} from "lucide-react";
import { Stats } from "@/lib/api";
import { AIActions } from "./AIActions";

interface Props {
  stats?: Stats;
  lastResponse?: {
    chunksSearched?: number;
    sourcesSearched?: number;
    citations?: number;
    searchTimeMs?: number;
  };
  relatedQuestions: string[];
  onQuestionClick: (q: string) => void;
  onAction?: (action: string) => void;
}

export function ChatSidebar({ stats, lastResponse, relatedQuestions, onQuestionClick, onAction }: Props) {
  const totalChunks = stats?.indexed_chunks ?? 0;
  const totalSources = stats?.total_sources ?? 0;

  const rows = [
    {
      icon: Layers,
      label: "Chunks Searched",
      value: lastResponse?.chunksSearched != null ? lastResponse.chunksSearched : "—",
      color: "#FF5C00",
    },
    {
      icon: Database,
      label: "Sources Used",
      value: lastResponse?.sourcesSearched != null ? lastResponse.sourcesSearched : "—",
      color: "#FF5C00",
    },
    {
      icon: Network,
      label: "Citations",
      value: lastResponse?.citations != null ? lastResponse.citations : "—",
      color: "#B96A00",
    },
    {
      icon: Clock,
      label: "Search Time",
      value:
        lastResponse?.searchTimeMs != null
          ? lastResponse.searchTimeMs >= 1000
            ? `${(lastResponse.searchTimeMs / 1000).toFixed(1)}s`
            : `${lastResponse.searchTimeMs}ms`
          : "—",
      color: "#FF5C00",
    },
    { icon: Layers, label: "Indexed Chunks", value: totalChunks, color: "#FF5C00" },
    { icon: Database, label: "Total Sources", value: totalSources, color: "#6B5B4D" },
  ];

  return (
    <div className="space-y-4">
      {/* Search Summary */}
      <motion.div
        initial={{ opacity: 0, x: 12 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ delay: 0.1 }}
        className="rounded-[16px] border-2 border-ink bg-card p-4"
      >
        <h3 className="mb-3 text-[12px] font-semibold text-foreground">Search Summary</h3>
        <div className="space-y-2.5">
          {rows.map((item) => (
            <div key={item.label} className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <item.icon className="h-3 w-3" style={{ color: item.color }} />
                <span className="text-[11px] text-muted">{item.label}</span>
              </div>
              <span className="text-[11px] font-semibold text-foreground">{item.value}</span>
            </div>
          ))}
        </div>
      </motion.div>

      {/* Related Questions */}
      <motion.div
        initial={{ opacity: 0, x: 12 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ delay: 0.2 }}
        className="rounded-[16px] border-2 border-ink bg-card p-4"
      >
        <h3 className="mb-3 text-[12px] font-semibold text-foreground">Related Questions</h3>
        <div className="space-y-2">
          {relatedQuestions.length > 0 ? (
            relatedQuestions.map((q, i) => (
              <motion.button
                key={i}
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.3 + i * 0.04 }}
                whileHover={{ x: 2 }}
                onClick={() => onQuestionClick(q)}
                className="flex w-full items-center gap-2 rounded-[10px] p-2.5 text-left text-[11px] text-foreground-3 transition-colors hover:bg-surface hover:text-foreground"
              >
                <HelpCircle className="h-3 w-3 flex-shrink-0 text-muted" />
                <span className="line-clamp-2">{q}</span>
              </motion.button>
            ))
          ) : (
            <>
              {[
                "What are the key insights from my notes?",
                "How does this connect to other sources?",
                "What are the main arguments presented?",
                "Can you compare this with my other content?",
              ].map((q, i) => (
                <motion.button
                  key={i}
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.3 + i * 0.04 }}
                  whileHover={{ x: 2 }}
                  onClick={() => onQuestionClick(q)}
                  className="flex w-full items-center gap-2 rounded-[10px] p-2.5 text-left text-[11px] text-foreground-3 transition-colors hover:bg-surface hover:text-foreground"
                >
                  <HelpCircle className="h-3 w-3 flex-shrink-0 text-muted" />
                  <span className="line-clamp-2">{q}</span>
                </motion.button>
              ))}
            </>
          )}
        </div>
      </motion.div>

      {/* Knowledge Graph Preview */}
      <motion.div
        initial={{ opacity: 0, x: 12 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ delay: 0.3 }}
        className="rounded-[16px] border-2 border-ink bg-card p-4"
      >
        <h3 className="mb-3 text-[12px] font-semibold text-foreground">Knowledge Graph Preview</h3>
        <div className="relative flex h-32 items-center justify-center overflow-hidden rounded-[12px] bg-surface">
          <svg width="160" height="100" viewBox="0 0 160 100">
            <circle cx="80" cy="50" r="8" fill="#FF5C00" opacity="0.9" />
            <circle cx="40" cy="30" r="5" fill="#FF5C00" opacity="0.7" />
            <circle cx="120" cy="30" r="5" fill="#E14E00" opacity="0.7" />
            <circle cx="40" cy="70" r="5" fill="#B96A00" opacity="0.7" />
            <circle cx="120" cy="70" r="5" fill="#B96A00" opacity="0.7" />
            <circle cx="80" cy="15" r="4" fill="#FF5C00" opacity="0.6" />
            <circle cx="80" cy="85" r="4" fill="#E14E00" opacity="0.6" />
            <line x1="80" y1="50" x2="40" y2="30" stroke="#FF5C00" strokeWidth="1" opacity="0.3" />
            <line x1="80" y1="50" x2="120" y2="30" stroke="#FF5C00" strokeWidth="1" opacity="0.3" />
            <line x1="80" y1="50" x2="40" y2="70" stroke="#FF5C00" strokeWidth="1" opacity="0.3" />
            <line x1="80" y1="50" x2="120" y2="70" stroke="#FF5C00" strokeWidth="1" opacity="0.3" />
            <line x1="80" y1="50" x2="80" y2="15" stroke="#FF5C00" strokeWidth="1" opacity="0.3" />
            <line x1="80" y1="50" x2="80" y2="85" stroke="#FF5C00" strokeWidth="1" opacity="0.3" />
          </svg>
        </div>
        <Link
          href="/stored"
          className="mt-3 flex w-full items-center justify-center gap-1.5 rounded-[10px] bg-[#FF5C00]/10 py-2 text-[11px] font-medium text-[#FF5C00] transition-colors hover:bg-[#FF5C00]/20"
        >
          Browse Stored Sources
          <ArrowRight className="h-3 w-3" />
        </Link>
      </motion.div>

      {/* AI Actions */}
      <motion.div
        initial={{ opacity: 0, x: 12 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ delay: 0.4 }}
      >
        <AIActions onAction={onAction} />
      </motion.div>
    </div>
  );
}

function HardDrive(props: any) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <line x1="22" x2="2" y1="12" y2="12" />
      <path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z" />
      <line x1="6" x2="6.01" y1="16" y2="16" />
      <line x1="10" x2="10.01" y1="16" y2="16" />
    </svg>
  );
}
