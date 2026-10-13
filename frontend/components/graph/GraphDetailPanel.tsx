"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowLeft, ArrowRight, MessageSquare, Search, X } from "lucide-react";
import { SOURCE_LABELS, sourceColor } from "./graphModel";

export interface PanelConnection {
  id: string;
  label: string;
  direction: "out" | "in";
  relation: string;
  sourceId?: string;
  sourceType: string;
  title?: string;
}

interface Props {
  label: string;
  count: number;
  degree: number;
  color: string;
  types: string[];
  connections: PanelConnection[];
  onSelect: (id: string) => void;
  onClose: () => void;
}

function truncate(text: string, max: number): string {
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}

export function GraphDetailPanel({
  label,
  count,
  degree,
  color,
  types,
  connections,
  onSelect,
  onClose,
}: Props) {
  const stats = [
    { value: count, label: count === 1 ? "mention" : "mentions" },
    { value: degree, label: degree === 1 ? "connection" : "connections" },
    { value: types.length, label: types.length === 1 ? "source type" : "source types" },
  ];

  return (
    <motion.aside
      initial={{ opacity: 0, x: 24 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 24 }}
      transition={{ duration: 0.22, ease: "easeOut" }}
      aria-label={`Details for ${label}`}
      className="absolute inset-x-2 bottom-2 z-30 flex max-h-[62%] flex-col rounded-xl border-2 border-ink bg-card text-foreground shadow-floating sm:static sm:inset-auto sm:max-h-none sm:w-[340px] sm:shrink-0 sm:rounded-xl"
    >
      <div className="flex items-start gap-2 border-b-2 border-ink p-4">
        <span
          aria-hidden
          className="mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full"
          style={{ background: color, boxShadow: `0 0 8px ${color}` }}
        />
        <div className="min-w-0 flex-1">
          <h2 className="break-words text-sm font-semibold leading-snug text-foreground">{label}</h2>
          <div className="mt-1 flex flex-wrap gap-1.5">
            {types.map((t) => (
              <span
                key={t}
                className="flex items-center gap-1 rounded-full border-2 border-ink bg-surface px-1.5 py-0.5 text-[10px] text-muted"
              >
                <span
                  aria-hidden
                  className="h-1.5 w-1.5 rounded-full"
                  style={{ background: sourceColor(t) }}
                />
                {SOURCE_LABELS[t] ?? t}
              </span>
            ))}
          </div>
        </div>
        <button
          onClick={onClose}
          aria-label="Close details"
          className="rounded-md p-1 text-muted transition-colors hover:bg-surface hover:text-foreground"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="grid grid-cols-3 gap-px border-b-2 border-ink bg-border">
        {stats.map((s) => (
          <div key={s.label} className="bg-card px-2 py-2.5 text-center">
            <div className="text-base font-semibold tabular-nums" style={{ color }}>
              {s.value}
            </div>
            <div className="text-[10px] text-muted">{s.label}</div>
          </div>
        ))}
      </div>

      <div className="flex gap-2 border-b-2 border-ink p-3">
        <Link
          href={`/search?q=${encodeURIComponent(label)}`}
          className="flex flex-1 items-center justify-center gap-1.5 rounded-lg border-2 border-ink bg-surface px-2 py-2 text-[11px] font-medium text-foreground-3 transition-colors hover:bg-surface-muted hover:text-foreground"
        >
          <Search className="h-3.5 w-3.5" />
          Search
        </Link>
        <Link
          href={`/chat?q=${encodeURIComponent(label)}`}
          className="flex flex-1 items-center justify-center gap-1.5 rounded-lg px-2 py-2 text-[11px] font-medium text-ink transition-opacity hover:opacity-90 shadow-sm"
          style={{ background: color }}
        >
          <MessageSquare className="h-3.5 w-3.5" />
          Ask AI
        </Link>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-3">
        <div className="mb-2 flex items-center justify-between px-1">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-subtle">
            Connections
          </span>
          <span className="text-[11px] text-subtle tabular-nums">{connections.length}</span>
        </div>

        {connections.length === 0 && (
          <p className="px-1 py-3 text-xs text-muted">
            No connections for this concept in the current filter.
          </p>
        )}

        <ul className="space-y-1.5">
          {connections.map((c) => {
            const outgoing = c.direction === "out";
            const Arrow = outgoing ? ArrowRight : ArrowLeft;
            return (
              <li key={`${c.direction}-${c.id}-${c.relation}-${c.sourceId ?? ""}`}>
                <button
                  onClick={() => onSelect(c.id)}
                  className="group w-full rounded-lg border border-transparent px-2 py-2 text-left transition-all hover:border-border hover:bg-surface"
                >
                  <div className="flex items-center gap-1.5">
                    <Arrow
                      className="h-3 w-3 shrink-0"
                      style={{ color: outgoing ? sourceColor(c.sourceType) : "var(--foreground-3)" }}
                    />
                    <span className="truncate text-[10px] font-medium uppercase tracking-wide text-brand">
                      {truncate(c.relation, 34)}
                    </span>
                  </div>
                  <div className="mt-0.5 truncate text-xs font-medium text-foreground group-hover:text-brand transition-colors">
                    {c.label}
                  </div>
                  {c.title && (
                    <div className="mt-0.5 flex items-center gap-1.5">
                      <span
                        aria-hidden
                        className="h-1.5 w-1.5 shrink-0 rounded-full"
                        style={{ background: sourceColor(c.sourceType) }}
                      />
                      <span className="truncate text-[10px] text-muted">{c.title}</span>
                    </div>
                  )}
                </button>
              </li>
            );
          })}
        </ul>
      </div>

      <p className="border-t-2 border-ink px-4 py-2.5 text-[10px] text-subtle">
        Click a connection to keep exploring →
      </p>
    </motion.aside>
  );
}
