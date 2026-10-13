"use client";

import { motion } from "framer-motion";
import {
  Youtube,
  Instagram,
  FileText,
  Files,
  Mic,
  Globe,
  Layers,
  SlidersHorizontal,
} from "lucide-react";
import { SOURCE_TYPES } from "@/lib/api";

interface Props {
  filter: string;
  setFilter: (f: string) => void;
  stats?: Record<string, number>;
}

const SOURCE_CONFIG: Record<string, { icon: typeof Youtube; label: string; color: string }> = {
  "": { icon: Layers, label: "All Sources", color: "#FF5C00" },
  youtube: { icon: Youtube, label: "YouTube", color: "#FF5C00" },
  instagram: { icon: Instagram, label: "Instagram", color: "#FF5C00" },
  pdf: { icon: FileText, label: "PDF", color: "#E14E00" },
  document: { icon: Files, label: "Document", color: "#E14E00" },
  audio: { icon: Mic, label: "Audio", color: "#E14E00" },
  web: { icon: Globe, label: "Web", color: "#B96A00" },
};

export function SourceFilterChips({ filter, setFilter, stats }: Props) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: 0.2 }}
      className="flex flex-wrap items-center gap-2"
    >
      {SOURCE_TYPES.map((f) => {
        const config = SOURCE_CONFIG[f] || SOURCE_CONFIG[""];
        const Icon = config.icon;
        const active = filter === f;
        const count = f === "" ? undefined : stats?.[f];

        return (
          <motion.button
            key={f || "all"}
            onClick={() => setFilter(f)}
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
            className={`flex items-center gap-2 rounded-full px-4 py-2 text-[12px] font-medium transition-all duration-200 ${
              active
                ? "bg-[#FF5C00] text-ink shadow-lg shadow-[#FF5C00]/20"
                : "border-2 border-ink bg-surface text-foreground-3 hover:bg-surface hover:text-foreground"
            }`}
          >
            <Icon
              className="h-3.5 w-3.5"
              style={{ color: active ? "white" : config.color }}
            />
            <span>{config.label}</span>
            {count !== undefined && count > 0 && (
              <span
                className={`rounded-full px-1.5 py-0.5 text-[10px] font-semibold ${
                  active
                    ? "bg-surface text-ink"
                    : "bg-surface text-muted"
                }`}
              >
                {count}
              </span>
            )}
          </motion.button>
        );
      })}

      <button className="ml-1 flex items-center gap-1.5 rounded-full border-2 border-ink bg-surface px-3 py-2 text-[12px] text-muted transition-all hover:bg-surface hover:text-foreground-3">
        <SlidersHorizontal className="h-3.5 w-3.5" />
        Filters
      </button>
    </motion.div>
  );
}
