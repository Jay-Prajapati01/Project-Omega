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
  Brain,
  CheckCircle,
  AlertCircle,
  Clock,
  Loader2,
} from "lucide-react";
import { processManager } from "@/lib/processManager";
import { getSourceTheme } from "@/lib/sourceTheme";

const TYPE_ICONS: Record<string, typeof Video> = {
  youtube: Video,
  instagram: Instagram,
  pdf: FileText,
  document: Files,
  documents: Files,
  audio: Music,
  web: Globe,
  file: Files,
};

interface ActivityEntry {
  id: string;
  type: string;
  title: string;
  description: string;
  timestamp: number;
  status: "running" | "completed" | "failed" | "cancelled";
  icon: typeof Video;
  color: string;
}

function timeAgo(ts: number) {
  const diff = Date.now() - ts;
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export function ActivityFeed() {
  const [activities, setActivities] = useState<ActivityEntry[]>([]);

  useEffect(() => {
    const buildFromProcesses = () => {
      const procs = processManager.getAllProcesses();
      const entries: ActivityEntry[] = procs
        .sort((a, b) => b.startedAt - a.startedAt)
        .slice(0, 8)
        .map((proc) => {
          const stepName = proc.events.filter((e) => e.event === "step_start").pop()?.data?.name || "";
          const Icon = TYPE_ICONS[proc.type] || Brain;
          const srcTheme = getSourceTheme(proc.type);

          let title = `${proc.type.charAt(0).toUpperCase() + proc.type.slice(1)} Processing`;
          let description = stepName || "Starting...";

          if (proc.status === "completed") {
            title = `${proc.type.charAt(0).toUpperCase() + proc.type.slice(1)} Indexed`;
            description = proc.result?.title || proc.title || "Completed successfully";
          } else if (proc.status === "failed") {
            title = `${proc.type.charAt(0).toUpperCase() + proc.type.slice(1)} Failed`;
            description = proc.error || "An error occurred";
          }

          return {
            id: proc.id,
            type: proc.type,
            title,
            description,
            timestamp: proc.startedAt,
            status: proc.status,
            icon: Icon,
            color: srcTheme.accent,
          };
        });
      setActivities(entries);
    };

    buildFromProcesses();
    let timeout: ReturnType<typeof setTimeout>;
    const debouncedBuild = () => {
      clearTimeout(timeout);
      timeout = setTimeout(buildFromProcesses, 300);
    };
    const unsub = processManager.subscribeAll(debouncedBuild);
    return () => { unsub(); clearTimeout(timeout); };
  }, []);

  if (activities.length === 0) {
    return (
      <div className="flex flex-col items-center py-8 text-center">
        <Clock className="mb-2 h-6 w-6 text-subtle" />
        <p className="text-[12px] text-muted">No recent activity</p>
        <p className="text-[10px] text-subtle">Process sources to see activity</p>
      </div>
    );
  }

  return (
    <div className="space-y-1">
      <AnimatePresence>
        {activities.map((activity, i) => {
          const Icon = activity.icon;
          return (
            <motion.div
              key={activity.id}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.05 }}
              className="flex items-center gap-3 rounded-[10px] p-2.5 transition-colors hover:bg-surface"
            >
              <div className="relative flex-shrink-0">
                <div
                  className="flex h-8 w-8 items-center justify-center rounded-[8px] bg-surface"
                >
                  <Icon className="h-4 w-4" style={{ color: activity.color }} />
                </div>
                {activity.status === "running" && (
                  <div className="absolute -bottom-0.5 -right-0.5">
                    <Loader2 className="h-3 w-3 animate-spin text-brand" />
                  </div>
                )}
                {activity.status === "completed" && (
                  <div className="absolute -bottom-0.5 -right-0.5">
                    <CheckCircle className="h-3 w-3 text-success" />
                  </div>
                )}
                {activity.status === "failed" && (
                  <div className="absolute -bottom-0.5 -right-0.5">
                    <AlertCircle className="h-3 w-3 text-danger" />
                  </div>
                )}
              </div>
              <div className="min-w-0 flex-1">
                <div className="text-[11px] font-medium text-foreground">{activity.title}</div>
                <div className="truncate text-[10px] text-muted">{activity.description}</div>
              </div>
              <span className="text-[9px] text-subtle flex-shrink-0">{timeAgo(activity.timestamp)}</span>
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}
