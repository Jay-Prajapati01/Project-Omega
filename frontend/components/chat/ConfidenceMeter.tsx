"use client";

import { motion } from "framer-motion";
import { Shield } from "lucide-react";

interface Props {
  citationsCount: number;
  sourcesCount?: number;
  chunksCount?: number;
}

export function ConfidenceMeter({ citationsCount, sourcesCount, chunksCount }: Props) {
  const hasCitations = citationsCount > 0;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.3 }}
      className="rounded-[16px] border-2 border-ink bg-card p-5"
    >
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Shield
            className="h-4 w-4"
            style={{ color: hasCitations ? "#FF5C00" : "#F59E0B" }}
          />
          <span className="text-[13px] font-semibold text-foreground">
            Answer Grounding
          </span>
        </div>
        <span
          className="text-[20px] font-bold tabular-nums"
          style={{ color: hasCitations ? "#FF5C00" : "#F59E0B" }}
        >
          {citationsCount}
        </span>
      </div>

      <p className="mb-3 text-[11px] text-muted">
        {hasCitations
          ? `This answer cites ${citationsCount} passage${citationsCount === 1 ? "" : "s"} from your knowledge base.`
          : "No citations were attached — treat this answer as ungrounded and verify against your sources."}
      </p>

      <div className="space-y-2 border-t-2 border-ink pt-3">
        <div className="text-[10px] font-semibold uppercase tracking-wider text-muted">
          Grounded by
        </div>
        <div className="grid grid-cols-3 gap-2">
          {[
            { label: "Citations", value: citationsCount },
            { label: "Sources", value: sourcesCount },
            { label: "Chunks", value: chunksCount },
          ].map((item) => (
            <div key={item.label} className="flex items-center gap-1.5">
              <span className="text-[10px] text-[#FF5C00]">✓</span>
              <span className="text-[11px] font-semibold text-foreground">
                {item.value != null ? item.value : "—"}
              </span>
              <span className="text-[10px] text-muted">{item.label}</span>
            </div>
          ))}
        </div>
      </div>
    </motion.div>
  );
}
