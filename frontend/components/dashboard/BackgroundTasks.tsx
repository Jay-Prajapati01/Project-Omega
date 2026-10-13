"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Video,
  FileText,
  Instagram,
  Music,
  Globe,
  Files,
  Loader2,
  CheckCircle,
} from "lucide-react";
import { processManager, ProcessState } from "@/lib/processManager";
import { getSourceTheme } from "@/lib/sourceTheme";

const TYPE_ICONS: Record<string, typeof Video> = {
  youtube: Video,
  instagram: Instagram,
  pdf: FileText,
  documents: Files,
  audio: Music,
  web: Globe,
  file: Files,
};

function getProgress(events: Array<{ event: string; data: Record<string, any> }>): number {
  let total = 0,
    done = 0;
  for (const evt of events) {
    if (evt.event === "step_start") total++;
    if (evt.event === "step_complete") done++;
    if (evt.event === "step_progress" && evt.data.progress) {
      done += evt.data.progress / 100;
    }
  }
  return total > 0 ? Math.round((done / total) * 100) : 0;
}

export function BackgroundTasks() {
  const [processes, setProcesses] = useState<ProcessState[]>([]);

  useEffect(() => {
    setProcesses(processManager.getActiveProcesses());
    let timeout: ReturnType<typeof setTimeout>;
    const debouncedUpdate = () => {
      clearTimeout(timeout);
      timeout = setTimeout(() => setProcesses(processManager.getActiveProcesses()), 300);
    };
    const unsub = processManager.subscribeAll(debouncedUpdate);
    return () => { unsub(); clearTimeout(timeout); };
  }, []);

  if (processes.length === 0) {
    return (
      <div className="flex flex-col items-center py-6 text-center">
        <div className="mb-2 flex h-10 w-10 items-center justify-center rounded-full bg-surface">
          <CheckCircle className="h-5 w-5 text-success" />
        </div>
        <p className="text-[12px] font-medium text-foreground">All caught up</p>
        <p className="text-[10px] text-muted">No active background tasks</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <AnimatePresence>
        {processes.map((proc) => {
          const Icon = TYPE_ICONS[proc.type] || Files;
          const srcTheme = getSourceTheme(proc.type);
          const progress = getProgress(proc.events);
          const currentStep = proc.events.filter((e) => e.event === "step_start").pop();
          const stepName = currentStep?.data?.name || "";

          return (
            <motion.div
              key={proc.id}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              className="rounded-[12px] border-2 border-ink bg-surface p-3"
            >
              <div className="flex items-center gap-2.5">
                <div
                  className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-[7px] bg-background"
                >
                  <Icon className="h-3.5 w-3.5" style={{ color: srcTheme.accent }} />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] font-medium text-foreground">
                      {srcTheme.name} Processing
                    </span>
                    <Loader2 className="h-3 w-3 animate-spin text-brand" />
                  </div>
                  {stepName && (
                    <p className="text-[10px] text-muted truncate">{stepName}</p>
                  )}
                </div>
                <span className="text-[11px] font-semibold tabular-nums text-brand">
                  {progress}%
                </span>
              </div>
              <div className="mt-2 h-1 overflow-hidden rounded-full bg-surface-muted">
                <motion.div
                  className="h-full rounded-full"
                  style={{ backgroundColor: srcTheme.accent }}
                  initial={{ width: 0 }}
                  animate={{ width: `${progress}%` }}
                  transition={{ duration: 0.3 }}
                />
              </div>
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}
