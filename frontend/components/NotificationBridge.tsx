"use client";

import { useEffect, useRef } from "react";
import { processManager, ProcessState } from "@/lib/processManager";
import { useAppStore } from "@/lib/store";

export function NotificationBridge() {
  const addNotification = useAppStore((s) => s.addNotification);
  const lastStatusRef = useRef<Map<string, string>>(new Map());

  useEffect(() => {
    const handleProcess = (proc: ProcessState) => {
      const prevStatus = lastStatusRef.current.get(proc.id);
      const currStatus = proc.status;

      if (prevStatus === currStatus) return;
      lastStatusRef.current.set(proc.id, currStatus);

      const typeLabel = proc.type.charAt(0).toUpperCase() + proc.type.slice(1);
      const title = proc.title || proc.fileName || proc.url || `${typeLabel} content`;

      if (currStatus === "running" && prevStatus !== "running") {
        addNotification({
          type: "processing_started",
          title: `${typeLabel} Processing`,
          description: `Started processing: ${title}`,
          sourceType: proc.type,
          sourceId: proc.id,
        });
      } else if (currStatus === "completed" && prevStatus !== "completed") {
        const chunks = proc.result?.chunks_stored || proc.result?.total_chunks || 0;
        addNotification({
          type: "processing_completed",
          title: `${typeLabel} Indexed`,
          description: `Completed: ${title}${chunks > 0 ? ` (${chunks} chunks)` : ""}`,
          sourceType: proc.type,
          sourceId: proc.id,
          href: `/${proc.type === "document" ? "documents" : proc.type}`,
        });
      } else if (currStatus === "failed" && prevStatus !== "failed") {
        addNotification({
          type: "processing_failed",
          title: `${typeLabel} Failed`,
          description: proc.error || `Failed to process: ${title}`,
          sourceType: proc.type,
          sourceId: proc.id,
        });
      }
    };

    const unsub = processManager.subscribeAll(handleProcess);
    return () => unsub();
  }, [addNotification]);

  return null;
}
