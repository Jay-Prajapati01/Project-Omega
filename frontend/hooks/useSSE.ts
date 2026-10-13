"use client";

import { useCallback, useEffect, useState } from "react";
import { processManager, ProcessState } from "@/lib/processManager";

export interface SSEEvent {
  event: string;
  data: Record<string, any>;
}

/**
 * Hook that connects to the global ProcessManager.
 * The SSE stream lives in the ProcessManager singleton, NOT in this hook.
 * This means processes survive navigation and page refresh.
 *
 * @param restoreType - If provided, will auto-restore the latest process of this type on mount
 */
export function useSSE(restoreType?: string) {
  const [events, setEvents] = useState<SSEEvent[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Record<string, any> | null>(null);
  const [processId, setProcessId] = useState<string | null>(null);
  const [startedAt, setStartedAt] = useState(0);

  // Restore latest process of given type on mount
  useEffect(() => {
    if (!restoreType) return;

    const allProcesses = processManager.getAllProcesses();
    const recent = allProcesses
      .filter((p) => p.type === restoreType)
      .sort((a, b) => b.startedAt - a.startedAt)[0];

    if (recent) {
      const age = Date.now() - recent.startedAt;
      if (age < 10 * 60 * 1000) {
        setProcessId(recent.id);
        setEvents(recent.events);
        setIsStreaming(recent.status === "running");
        setError(recent.error);
        setResult(recent.result);
        setStartedAt(recent.startedAt);
      }
    }
  }, [restoreType]);

  // Subscribe to process changes when processId changes
  useEffect(() => {
    if (!processId) return;

    const proc = processManager.getProcess(processId);
    if (proc) {
      setEvents(proc.events);
      setIsStreaming(proc.status === "running");
      setError(proc.error);
      setResult(proc.result);
      setStartedAt(proc.startedAt);
    }

    const unsub = processManager.subscribe(processId, (state: ProcessState) => {
      setEvents(state.events);
      setIsStreaming(state.status === "running");
      setError(state.error);
      setResult(state.result);
      setStartedAt(state.startedAt);
    });

    return unsub;
  }, [processId]);

  const startStream = useCallback(
    (url: string, body: Record<string, any>, meta?: { fileName?: string; url?: string; title?: string }) => {
      const id = `process_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
      const now = Date.now();

      setEvents([]);
      setError(null);
      setResult(null);
      setIsStreaming(true);
      setProcessId(id);
      setStartedAt(now);

      processManager.startProcess(id, body.source_type || restoreType || "unknown", url, body, undefined, meta);
    },
    [restoreType]
  );

  const startFileStream = useCallback(
    (url: string, file: File, meta?: { fileName?: string; url?: string; title?: string }) => {
      const id = `process_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
      const now = Date.now();

      setEvents([]);
      setError(null);
      setResult(null);
      setIsStreaming(true);
      setProcessId(id);
      setStartedAt(now);

      processManager.startProcess(id, restoreType || "file", url, undefined, file, {
        fileName: file.name,
        ...meta,
      });
    },
    [restoreType]
  );

  const cancel = useCallback(() => {
    if (processId) {
      processManager.cancelProcess(processId);
      setIsStreaming(false);
    }
  }, [processId]);

  return { events, isStreaming, error, result, startStream, startFileStream, cancel, processId, startedAt };
}

/**
 * Hook to show a global banner of all active processes.
 */
export function useActiveProcesses() {
  const [processes, setProcesses] = useState<ProcessState[]>([]);

  useEffect(() => {
    setProcesses(processManager.getActiveProcesses());
    let timeout: ReturnType<typeof setTimeout>;
    const debouncedUpdate = () => {
      clearTimeout(timeout);
      timeout = setTimeout(() => setProcesses(processManager.getActiveProcesses()), 200);
    };
    const unsub = processManager.subscribeAll(debouncedUpdate);
    return () => { unsub(); clearTimeout(timeout); };
  }, []);

  return processes;
}
