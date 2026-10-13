"use client";

import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  Database,
  Brain,
  Activity,
  Server,
} from "lucide-react";
import { getDetailedHealth } from "@/lib/api";

interface StatusItem {
  label: string;
  value: string;
  icon: typeof Brain;
  color: string;
  status: "healthy" | "busy" | "offline";
}

export function LiveSystemStatus() {
  const { data: health, isError, isLoading } = useQuery({
    queryKey: ["health", "detailed"],
    queryFn: getDetailedHealth,
    refetchInterval: 30000,
    retry: 1,
  });

  const ok = (check: string) => health?.checks?.[check] === "ok";

  const statuses: StatusItem[] = [
    {
      label: "API",
      value: isLoading ? "Checking…" : health?.app ?? "Unknown",
      icon: Server,
      color: isError ? "var(--danger)" : health ? "var(--success)" : "var(--warning)",
      status: isError ? "offline" : health ? "healthy" : "busy",
    },
    {
      label: "LLM",
      value: health?.llm_model ?? "Unknown",
      icon: Brain,
      color: "var(--brand)",
      status: ok("ollama") ? "healthy" : "offline",
    },
    {
      label: "Embeddings",
      value: health?.embedding_model ?? "Unknown",
      icon: Activity,
      color: "var(--success)",
      status: ok("ollama") ? "healthy" : "offline",
    },
    {
      label: "Vector DB",
      value: health?.collection ?? "Unknown",
      icon: Database,
      color: "var(--info)",
      status: ok("qdrant") ? "healthy" : "offline",
    },
  ];

  return (
    <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
      {statuses.map((item, i) => {
        const Icon = item.icon;
        return (
          <motion.div
            key={item.label}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 * i }}
            className="rounded-[12px] border-2 border-ink bg-surface p-3"
          >
            <div className="mb-2 flex items-center justify-between">
              <div
                className="flex h-6 w-6 items-center justify-center rounded-[6px] bg-background"
              >
                <Icon className="h-3.5 w-3.5" style={{ color: item.color }} />
              </div>
              <span
                className={`flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[8px] font-semibold ${
                  item.status === "healthy"
                    ? "bg-success/10 text-success"
                    : item.status === "busy"
                    ? "bg-warning/10 text-warning"
                    : "bg-danger/10 text-danger"
                }`}
              >
                <span
                  className={`h-1 w-1 rounded-full ${
                    item.status === "healthy"
                      ? "bg-success"
                      : item.status === "busy"
                      ? "bg-warning"
                      : "bg-danger"
                  }`}
                />
                {item.status}
              </span>
            </div>
            <div className="text-[10px] font-medium text-foreground">{item.label}</div>
            <div className="truncate text-[9px] text-muted">{item.value}</div>
          </motion.div>
        );
      })}
    </div>
  );
}
