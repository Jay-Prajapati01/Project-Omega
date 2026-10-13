"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { ExternalLink } from "lucide-react";
import { API_URL } from "@/lib/api";

interface Props {
  index: number;
  sourceTitle: string;
  sourceType: string;
  snippet: string;
  url?: string;
}

export function InlineCitation({ index, sourceTitle, sourceType, snippet, url }: Props) {
  const [hovered, setHovered] = useState(false);

  return (
    <span
      className="relative inline-block"
      title={`Source ${index}: ${sourceTitle}`}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <span className="mx-0.5 inline-flex max-w-[240px] cursor-pointer items-center gap-1 rounded-full bg-[#FF5C00]/10 px-2 py-0.5 align-baseline text-[10px] font-semibold text-[#A83D00] transition-colors hover:bg-[#FF5C00]/20 dark:text-[#FF9A61]">
        <span className="shrink-0 capitalize">{sourceType}</span>
        <span aria-hidden="true">·</span>
        <span className="truncate">{sourceTitle}</span>
      </span>

      {hovered && (
        <motion.div
          initial={{ opacity: 0, y: 4, scale: 0.95 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          className="absolute bottom-full left-1/2 z-50 mb-2 w-72 -translate-x-1/2 overflow-hidden rounded-[12px] border-2 border-ink bg-surface p-3 shadow-xl shadow-black/30"
        >
          <div className="mb-1.5 flex items-center gap-1.5">
            <span className="rounded-full bg-[#FF5C00]/15 px-1.5 py-0.5 text-[9px] font-semibold text-[#FF5C00] capitalize">
              {sourceType}
            </span>
            {url && (
              (() => {
                if (url.startsWith("/source/")) return url;
                if (url.startsWith("/")) {
                  return `${API_URL}${url}`;
                }
                try {
                  const u = new URL(url);
                  if (u.protocol === "http:" || u.protocol === "https:") {
                    return url;
                  }
                } catch {
                  return null;
                }
                return null;
              })() && (
                <a
                  href={
                    (url.startsWith("http") || url.startsWith("/source/"))
                      ? url
                      : `${API_URL}${url}`
                  }
                  target={url.startsWith("http") ? "_blank" : "_self"}
                  rel="noopener noreferrer"
                  className="ml-auto flex items-center gap-0.5 text-[9px] text-[#B96A00] hover:text-[#B96A00] transition-colors"
                >
                  Open <ExternalLink className="h-2.5 w-2.5" />
                </a>
              )
            )}
          </div>
          <div className="mb-1 text-[11px] font-medium text-foreground">{sourceTitle}</div>
          <div className="text-[10px] leading-relaxed text-foreground-3 line-clamp-2">
            &ldquo;{snippet}&rdquo;
          </div>
        </motion.div>
      )}
    </span>
  );
}
