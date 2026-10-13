"use client";

import { motion } from "framer-motion";
import {
  StickyNote,
  BookOpen,
  FileDown,
  GitCompare,
  Network,
  Languages,
  HelpCircle,
  Sparkles,
} from "lucide-react";

const ACTIONS = [
  { icon: StickyNote, label: "Create Notes", color: "#FF5C00" },
  { icon: BookOpen, label: "Generate Flashcards", color: "#FF5C00" },
  { icon: FileDown, label: "Export Markdown", color: "#B96A00" },
  { icon: GitCompare, label: "Compare Sources", color: "#F59E0B" },
  { icon: Network, label: "Visualize as Graph", color: "#FF5C00" },
  { icon: Languages, label: "Explain Simply", color: "#E14E00" },
];

interface Props {
  onAction?: (action: string) => void;
}

export function AIActions({ onAction }: Props) {
  return (
    <div className="space-y-2">
      <h3 className="text-[11px] font-semibold uppercase tracking-wider text-muted">
        AI Actions
      </h3>
      <div className="grid grid-cols-2 gap-2">
        {ACTIONS.map((action, i) => (
          <motion.button
            key={action.label}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 + i * 0.04 }}
            whileHover={{ scale: 1.02, y: -1 }}
            whileTap={{ scale: 0.98 }}
            onClick={() => onAction?.(action.label)}
            className="flex items-center gap-2.5 rounded-[12px] border-2 border-ink bg-surface p-3 text-left transition-all hover:border-border hover:bg-surface"
          >
            <div
              className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-[8px]"
              style={{ backgroundColor: `${action.color}15` }}
            >
              <action.icon className="h-3.5 w-3.5" style={{ color: action.color }} />
            </div>
            <span className="text-[11px] font-medium text-foreground-3">{action.label}</span>
          </motion.button>
        ))}
      </div>

      <motion.button
        whileHover={{ scale: 1.01 }}
        whileTap={{ scale: 0.99 }}
        className="flex w-full items-center justify-center gap-2 rounded-[14px] border-2 border-ink bg-surface p-3 text-[11px] font-medium text-foreground-3 transition-all hover:bg-surface hover:text-foreground"
      >
        <HelpCircle className="h-3.5 w-3.5" />
        Ask a Follow-up
      </motion.button>
    </div>
  );
}
