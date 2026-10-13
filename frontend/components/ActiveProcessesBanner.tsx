"use client";

import { useActiveProcesses } from "@/hooks/useSSE";
import { processManager } from "@/lib/processManager";
import { getSourceTheme } from "@/lib/sourceTheme";
import { Video, Camera, X, Loader2, CheckCircle, AlertCircle } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import Link from "next/link";

const TYPE_CONFIG: Record<string, { icon: any; sourceType: string; label: string; href: string }> = {
  youtube: { icon: Video, sourceType: "youtube", label: "YouTube", href: "/youtube" },
  instagram: { icon: Camera, sourceType: "instagram", label: "Instagram", href: "/instagram" },
  unknown: { icon: Video, sourceType: "youtube", label: "Process", href: "/stored" },
};

function getProgress(events: Array<{ event: string; data: Record<string, any> }>): number {
  const steps = new Map<number, { done: boolean; progress: number }>();
  let totalSteps = 0;
  for (const evt of events) {
    const step = Number(evt.data?.step || 0);
    if (evt.data?.total_steps) totalSteps = Math.max(totalSteps, Number(evt.data.total_steps));
    if (!step) continue;
    const cur = steps.get(step) || { done: false, progress: 0 };
    if (evt.event === "step_complete") steps.set(step, { done: true, progress: 100 });
    else if (evt.event === "step_fail") steps.set(step, { done: true, progress: 100 });
    else if (evt.event === "step_progress") {
      steps.set(step, { done: false, progress: Math.max(cur.progress, Number(evt.data.progress) || 0) });
    } else if (!steps.has(step)) {
      steps.set(step, cur);
    }
  }
  if (steps.size === 0) return 0;
  let done = 0;
  for (const s of steps.values()) done += s.done ? 1 : s.progress / 100;
  const denominator = Math.max(totalSteps, steps.size);
  return Math.min(100, Math.round((done / denominator) * 100));
}

export function ActiveProcessesBanner() {
  const processes = useActiveProcesses();

  if (processes.length === 0) return null;

  return (
    <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-50 flex flex-col gap-2 max-w-[600px] w-full px-4">
      <AnimatePresence>
        {processes.map((proc) => {
          const config = TYPE_CONFIG[proc.type] || TYPE_CONFIG.unknown;
          const srcTheme = getSourceTheme(config.sourceType);
          const Icon = config.icon;
          const progress = getProgress(proc.events);
          const currentStep = proc.events.filter(e => e.event === "step_start").pop();
          const stepName = currentStep?.data?.name || "";

          return (
            <motion.div
              key={proc.id}
              initial={{ opacity: 0, y: 20, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 20, scale: 0.95 }}
              className="rounded-[16px] border-2 border-ink bg-card/95 backdrop-blur-xl shadow-floating p-3 text-foreground"
            >
              <div className="flex items-center gap-3">
                <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-[10px]" style={{ backgroundColor: srcTheme.softDark }}>
                  <Icon className="h-4 w-4" style={{ color: srcTheme.accent }} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-[12px] font-semibold text-foreground truncate">
                      {proc.fileName || proc.url || `${config.label} Processing`}
                    </span>
                    {proc.status === "running" && (
                      <Loader2 className="h-3 w-3 text-brand animate-spin flex-shrink-0" />
                    )}
                    {proc.status === "completed" && (
                      <CheckCircle className="h-3 w-3 text-success flex-shrink-0" />
                    )}
                    {proc.status === "failed" && (
                      <AlertCircle className="h-3 w-3 text-danger flex-shrink-0" />
                    )}
                  </div>
                  {proc.status === "running" && stepName && (
                    <p className="text-[10px] text-muted truncate">{stepName}</p>
                  )}
                  {proc.status === "failed" && (
                    <p className="text-[10px] text-danger truncate">{proc.error}</p>
                  )}
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  {proc.status === "running" && (
                    <span className="text-[11px] font-medium tabular-nums text-brand">{progress}%</span>
                  )}
                  <Link
                    href={config.href}
                    className="text-[10px] text-foreground-3 hover:text-foreground transition-colors px-2 py-1 rounded-md hover:bg-surface"
                  >
                    View
                  </Link>
                  <button
                    onClick={() => processManager.removeProcess(proc.id)}
                    className="p-1 rounded-md hover:bg-surface text-subtle hover:text-foreground transition-colors"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </div>
              </div>
              {proc.status === "running" && (
                <div className="mt-2 h-1 rounded-full bg-surface overflow-hidden">
                  <motion.div
                    className="h-full rounded-full"
                    style={{ backgroundColor: srcTheme.accent }}
                    initial={{ width: 0 }}
                    animate={{ width: `${progress}%` }}
                    transition={{ duration: 0.3 }}
                  />
                </div>
              )}
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}
