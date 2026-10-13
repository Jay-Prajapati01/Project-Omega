"use client";

import { memo } from "react";
import { Handle, Position, type NodeProps } from "reactflow";
import { cleanLabel } from "./graphModel";

export interface ConceptData {
  label: string;
  count: number;
  degree: number;
  color: string;
  hub: boolean;
  active: boolean;
}

function truncate(text: string, max: number): string {
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}

function ConceptNodeInner({ data, selected }: NodeProps<ConceptData>) {
  const { label, count, degree, color, hub, active } = data;
  const on = active || selected;
  const clean = cleanLabel(label);
  const display = truncate(clean, hub ? 30 : 28);

  return (
    <div
      title={`${clean}\n${degree} connection${degree === 1 ? "" : "s"}${
        count > 1 ? ` · mentioned ${count}×` : ""
      }`}
      aria-label={`Concept: ${clean}, ${degree} connections`}
      className={`flex items-center gap-1.5 overflow-hidden rounded-full border-2 px-2.5 py-1.5 transition-[border-color,box-shadow] duration-150 ${
        hub ? "max-w-[320px] text-[15px]" : "max-w-[290px] text-[14px]"
      } ${on ? "font-medium" : "font-normal"}`}
      style={{
        borderColor: on ? color : `${color}80`,
        background: hub
          ? `linear-gradient(135deg, ${color}59 0%, var(--card) 65%)`
          : `linear-gradient(135deg, ${color}30 0%, var(--card) 65%)`,
        color: "var(--foreground)",
        boxShadow: on
          ? `0 0 0 3px ${color}33, 0 0 22px ${color}66`
          : hub
            ? `0 0 14px ${color}40`
            : "none",
      }}
    >
      <Handle
        type="target"
        position={Position.Left}
        isConnectable={false}
        className="pointer-events-none !opacity-0"
      />
      <span
        aria-hidden
        className="h-2 w-2 shrink-0 rounded-full"
        style={{ background: color, boxShadow: on ? `0 0 6px ${color}` : "none" }}
      />
      <span className="whitespace-nowrap">{display}</span>
      {count > 1 && (
        <span
          className="shrink-0 rounded-full px-1.5 py-px text-[11px] font-semibold tabular-nums"
          style={{ background: `${color}2e`, color: color }}
        >
          {count}
        </span>
      )}
      <Handle
        type="source"
        position={Position.Right}
        isConnectable={false}
        className="pointer-events-none !opacity-0"
      />
    </div>
  );
}

export const ConceptNode = memo(ConceptNodeInner);
