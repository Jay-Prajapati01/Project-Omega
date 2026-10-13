"use client";

import { motion } from "framer-motion";
import { AlertTriangle, RefreshCw, Search, HelpCircle, ArrowRight } from "lucide-react";

interface Props {
  error: string;
  onRetry: () => void;
  onBroaden: () => void;
}

export function ChatErrorState({ error, onRetry, onBroaden }: Props) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex flex-col items-center py-12"
    >
      <div className="mb-6 flex h-20 w-20 items-center justify-center rounded-[20px] bg-danger/10">
        <AlertTriangle className="h-10 w-10 text-danger" />
      </div>

      <h2 className="mb-2 text-[18px] font-bold text-foreground">
        Couldn&apos;t generate a grounded answer
      </h2>
      <p className="mb-6 max-w-md text-center text-[13px] text-muted">
        The AI couldn&apos;t find enough relevant information to generate a confident
        response. This usually means the question is too specific or your knowledge
        base doesn&apos;t have matching content yet.
      </p>

      <div className="mb-6 max-w-sm space-y-2">
        <h3 className="text-[11px] font-semibold uppercase tracking-wider text-muted">
          Suggestions
        </h3>
        {[
          { icon: Search, label: "Broaden your search terms", action: onBroaden },
          { icon: HelpCircle, label: "Try asking differently", action: onRetry },
          { icon: ArrowRight, label: "Add more content to your knowledge base", action: () => {} },
        ].map((s, i) => (
          <button
            key={i}
            onClick={s.action}
            className="flex w-full items-center gap-3 rounded-[12px] border-2 border-ink bg-surface p-3 text-left text-[12px] text-foreground-3 transition-all hover:bg-surface hover:text-foreground"
          >
            <s.icon className="h-3.5 w-3.5 text-muted" />
            {s.label}
          </button>
        ))}
      </div>

      <motion.button
        whileHover={{ scale: 1.01 }}
        whileTap={{ scale: 0.99 }}
        onClick={onRetry}
        className="flex items-center gap-2 rounded-[14px] bg-[#FF5C00] border-2 border-ink px-5 py-3 text-[13px] font-semibold text-ink transition-all hover:bg-[#E14E00]"
      >
        <RefreshCw className="h-4 w-4" />
        Try Again
      </motion.button>
    </motion.div>
  );
}
