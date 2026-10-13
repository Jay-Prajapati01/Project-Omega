/**
 * Global Process Manager — singleton that manages SSE connections
 * independently of React component lifecycle.
 *
 * Processes survive page navigation and can be reconnected on refresh.
 */

import { API_URL, api } from "./api";
import { useAppStore } from "./store";
import { authHeaders, cloudMode } from "./auth";

export interface ProcessState {
  id: string;
  type: string; // "pdf" | "youtube" | "instagram" | "documents" | "audio" | "web"
  status: "running" | "completed" | "failed" | "cancelled";
  events: Array<{ event: string; data: Record<string, any> }>;
  result: Record<string, any> | null;
  error: string | null;
  startedAt: number;
  fileName?: string;
  url?: string;
  title?: string;
  jobId?: string;
  jobPhase?: string; // last known cloud phase: "queued" | "processing"
}

type ProcessListener = (process: ProcessState) => void;

class ProcessManager {
  private static instance: ProcessManager;
  private processes: Map<string, ProcessState> = new Map();
  private abortControllers: Map<string, AbortController> = new Map();
  private listeners: Map<string, Set<ProcessListener>> = new Map();
  private globalListeners: Set<ProcessListener> = new Set();

  static getInstance(): ProcessManager {
    if (!ProcessManager.instance) {
      ProcessManager.instance = new ProcessManager();
    }
    return ProcessManager.instance;
  }

  resetForAccountChange(): void {
    if (this._persistTimer) clearTimeout(this._persistTimer);
    this._persistTimer = null;
    this.restored = false;
    this.abortControllers.forEach(controller => controller.abort());
    this.abortControllers.clear();
    this.processes.clear();
    this.listeners.clear();
    this.globalListeners.clear();
  }

  /** Subscribe to a specific process */
  subscribe(processId: string, listener: ProcessListener): () => void {
    if (!this.listeners.has(processId)) {
      this.listeners.set(processId, new Set());
    }
    this.listeners.get(processId)!.add(listener);
    return () => {
      this.listeners.get(processId)?.delete(listener);
    };
  }

  /** Subscribe to all process changes */
  subscribeAll(listener: ProcessListener): () => void {
    this.globalListeners.add(listener);
    return () => {
      this.globalListeners.delete(listener);
    };
  }

  private notify(processId: string) {
    const process = this.processes.get(processId);
    if (!process) return;
    const snapshot = { ...process, events: [...process.events] };
    this.listeners.get(processId)?.forEach((l) => l(snapshot));
    this.globalListeners.forEach((l) => l(snapshot));
  }

  /** Get current state of a process */
  getProcess(processId: string): ProcessState | undefined {
    return this.processes.get(processId);
  }

  /** Get all processes */
  getAllProcesses(): ProcessState[] {
    this.restore();
    return Array.from(this.processes.values());
  }

  /** Get active (running) processes */
  getActiveProcesses(): ProcessState[] {
    return this.getAllProcesses().filter((p) => p.status === "running");
  }

  /** Start a new SSE stream process */
  startProcess(
    processId: string,
    type: string,
    url: string,
    body?: Record<string, any>,
    file?: File,
    meta?: { fileName?: string; url?: string; title?: string }
  ): void {
    // Abort existing process with same ID
    this.abortProcess(processId);

    const state: ProcessState = {
      id: processId,
      type,
      status: "running",
      events: [],
      result: null,
      error: null,
      startedAt: Date.now(),
      fileName: meta?.fileName,
      url: meta?.url,
      title: meta?.title,
    };
    this.processes.set(processId, state);
    this.persist();
    this.notify(processId);

    const abort = new AbortController();
    this.abortControllers.set(processId, abort);

    this._stream(processId, url, body, file, abort);
  }

  private async _stream(
    processId: string,
    url: string,
    body?: Record<string, any>,
    file?: File,
    abort?: AbortController
  ) {
    try {
      let res: Response;
      const apiKey = useAppStore.getState().settings.apiKey;
      const headers: Record<string, string> = apiKey ? { "X-API-Key": apiKey } : {};
      Object.assign(headers, await authHeaders());
      headers["Idempotency-Key"] = processId;
      if (file) {
        const formData = new FormData();
        formData.append("file", file);
        res = await fetch(url, {
          method: "POST",
          headers,
          body: formData,
          signal: abort?.signal,
        });
      } else {
        res = await fetch(url, {
          method: "POST",
          headers: { ...headers, "Content-Type": "application/json" },
          body: JSON.stringify(body || {}),
          signal: abort?.signal,
        });
      }

      if (!res.ok) {
        const errData = await res.json().catch(() => ({ detail: "Request failed" }));
        throw new Error(errData.detail || `HTTP ${res.status}`);
      }

      const cloudJob = res.headers.get("X-Job-ID");
      if (cloudMode && cloudJob) {
        const proc = this.processes.get(processId);
        if (proc) proc.jobId = cloudJob;
        await res.body?.cancel();
        await this.pollJob(processId, cloudJob);
        return;
      }
      const reader = res.body?.getReader();
      if (!reader) throw new Error("No response body");

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        let currentEvent = "";
        for (const line of lines) {
          if (line.startsWith("event: ")) {
            currentEvent = line.slice(7).trim();
          } else if (line.startsWith("data: ")) {
            const dataStr = line.slice(6);
            try {
              const data = JSON.parse(dataStr);
              const evt = { event: currentEvent || "message", data };
              this._addEvent(processId, evt);
            } catch {
              // skip non-JSON
            }
            currentEvent = "";
          }
        }
      }

      // Stream ended normally
      const proc = this.processes.get(processId);
      if (proc && proc.status === "running") {
        proc.status = "completed";
        this.persist();
        this.notify(processId);
      }
    } catch (err: any) {
      if (err.name === "AbortError") {
        const proc = this.processes.get(processId);
        if (proc) {
          proc.status = "cancelled";
          this.persist();
          this.notify(processId);
        }
        return;
      }
      const proc = this.processes.get(processId);
      if (proc) {
        proc.status = "failed";
        proc.error = err.message || "Stream connection lost";
        this.persist();
        this.notify(processId);
      }
    }
  }

  private _addEvent(processId: string, evt: { event: string; data: Record<string, any> }) {
    const proc = this.processes.get(processId);
    if (!proc) return;

    proc.events = [...proc.events, evt];
    if (evt.event === "queued") proc.jobId = evt.data.job_id;

    if (evt.event === "complete") {
      proc.result = evt.data;
      proc.status = "completed";
    } else if (evt.event === "error" || evt.event === "step_fail") {
      proc.error = evt.data.error || "Unknown error";
      proc.status = "failed";
    }

    this.persist();
    this.notify(processId);
  }

  private polling = new Set<string>();
  private async pollJob(processId: string, jobId: string) {
    if (this.polling.has(processId)) return;
    this.polling.add(processId);
    // Exponential backoff (2s -> 30s cap): quiet on long Cloud Run Job
    // executions instead of hammering /jobs every 2 seconds for hours.
    let attempt = 0;
    try {
      while (this.processes.get(processId)?.status === "running") {
        const { data } = await api.get(`/jobs/${jobId}`);
        if (data.status === "completed") {
          this._addEvent(processId, { event: "complete", data: data.result }); return;
        }
        if (data.status === "failed" || data.status === "cancelled") {
          this._addEvent(processId, { event: "error", data: { error: data.error?.message || "Job cancelled" } }); return;
        }
        const proc = this.processes.get(processId);
        if (proc && (data.status === "queued" || data.status === "processing") && proc.jobPhase !== data.status) {
          proc.jobPhase = data.status;
          this._addEvent(processId, { event: "phase", data: { phase: data.status } });
        }
        attempt += 1;
        const delay = Math.min(2000 * Math.pow(1.6, attempt - 1), 30000);
        await new Promise(resolve => setTimeout(resolve, delay));
      }
    } catch (err) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      const message =
        status === 401
          ? "Your session expired. Sign in again to keep tracking this job."
          : "Unable to read cloud job status. Refresh to reconnect.";
      this._addEvent(processId, { event: "error", data: { error: message } });
    } finally { this.polling.delete(processId); }
  }

  /** Cancel a running process */
  abortProcess(processId: string) {
    const abort = this.abortControllers.get(processId);
    if (abort) {
      abort.abort();
      this.abortControllers.delete(processId);
    }
  }

  /** Cancel and remove a process */
  async cancelProcess(processId: string) {
    const existing = this.processes.get(processId);
    if (cloudMode && existing?.jobId) {
      try { await api.delete(`/jobs/${existing.jobId}`); }
      catch { existing.error = "This job is already processing and cannot be cancelled."; this.notify(processId); return; }
    }
    this.abortProcess(processId);
    const proc = this.processes.get(processId);
    if (proc) {
      proc.status = "cancelled";
      this.persist();
      this.notify(processId);
    }
  }

  /** Remove a process from tracking */
  removeProcess(processId: string) {
    this.abortProcess(processId);
    this.processes.delete(processId);
    this.listeners.delete(processId);
    this.persist();
  }

  /** Persist to localStorage (debounced) */
  private _persistTimer: ReturnType<typeof setTimeout> | null = null;
  private persist() {
    if (this._persistTimer) return;
    this._persistTimer = setTimeout(() => {
      this._persistTimer = null;
      try {
        const data = Array.from(this.processes.entries()).map(([id, state]) => [id, {
          ...(cloudMode ? { id: state.id, type: state.type, status: state.status, startedAt: state.startedAt,
             jobId: state.jobId, events: [], result: null, error: null } : {

          ...state,
          events: state.events.slice(-100),
          }),
        }]);
        localStorage.setItem("mindmesh-processes", JSON.stringify(data));
      } catch {
        // localStorage full or unavailable
      }
    }, 500);
  }

  /** Restore from localStorage on page load (idempotent — safe to call often) */
  private restored = false;
  restore() {
    if (this.restored) return;
    this.restored = true;
    try {
      const raw = localStorage.getItem("mindmesh-processes");
      if (!raw) return;
      const data = JSON.parse(raw);
      for (const [id, state] of data) {
        if (this.processes.has(id)) continue; // already live in this session
        // The SSE stream cannot resume after a reload — surface that honestly
        // instead of showing a spinner that never moves.
        if (cloudMode && state.jobId && (state.status === "running" || state.status === "failed")) {
          state.status = "running";
          this.processes.set(id, state);
          void this.pollJob(id, state.jobId);
          continue;
        }
        if (state.status === "running") {
          state.status = "failed";
          state.error =
            Date.now() - state.startedAt > 30 * 60 * 1000
              ? "Process timed out (page was refreshed or navigated away)"
              : "Interrupted by page refresh";
        }
        this.processes.set(id, state);
      }
    } catch {
      // corrupted data / SSR (no localStorage)
    }
  }
}

export const processManager = ProcessManager.getInstance();
