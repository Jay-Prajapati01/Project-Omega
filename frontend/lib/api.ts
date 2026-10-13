import axios from "axios";
import { useAppStore } from "./store";
import { authHeaders, cloudMode } from "./auth";
import { getSupabase } from "./supabaseClient";
import { trackFeatureUse } from "./analytics";

export const API_URL = (
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
  // Callers all append "/api" themselves; tolerate an env value that
  // already includes the prefix instead of producing ".../api/api".
).replace(/\/+api\/+$/, "").replace(/\/+api$/, "");

export const api = axios.create({
  baseURL: `${API_URL}/api`,
  headers: { "Content-Type": "application/json" },
});

// Attach X-API-Key from settings store on every mutating request
api.interceptors.request.use(async (config) => {
  // Public endpoints (e.g. the contact form) must work signed-out — the auth
  // helper intentionally throws when there is no session, so bypass it there.
  if ((config.url ?? "").startsWith("/contact") || (config.url ?? "").startsWith("/v1/public/")) return config;
  Object.assign(config.headers, await authHeaders());
  const state = useAppStore.getState();
  if (state.settings.apiKey) {
    config.headers = config.headers || {};
    config.headers["X-API-Key"] = state.settings.apiKey;
  }
  return config;
});

// Session expiry handling: on a 401, try exactly one silent refresh with
// Supabase; if that fails, sign out so the auth gate takes over instead of
// leaving the user with silent failures (audit: expired-session UX).
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    if (
      error.response?.status === 401 &&
      original &&
      !original._sessionRetried
    ) {
      original._sessionRetried = true;
      try {
        const { data } = await getSupabase().auth.refreshSession();
        if (data.session) {
          original.headers = {
            ...original.headers,
            Authorization: `Bearer ${data.session.access_token}`,
          };
          return api.request(original);
        }
      } catch {
        // fall through to sign-out
      }
      try {
        await getSupabase().auth.signOut();
      } catch {
        // ignore: the gate handles the signed-out state
      }
    }
    return Promise.reject(error);
  }
);

// Queue acknowledgements are polled behind the existing typed API functions.
// Backoff (2s -> 30s cap) keeps long Cloud Run Job executions cheap; the
// persisted job id lets ProcessManager resume tracking after a refresh.
api.interceptors.response.use(async (response) => {
  if (response.status !== 202 || !response.data?.job_id) return response;
  const jobId = response.data.job_id;
  try { localStorage.setItem("mindmesh-last-job", jobId); } catch { /* SSR/private mode */ }
  const deadline = Date.now() + 4 * 60 * 60 * 1000;
  let attempt = 0;
  while (Date.now() < deadline) {
    attempt += 1;
    await new Promise(resolve => setTimeout(resolve, Math.min(2000 * Math.pow(1.6, attempt - 1), 30000)));
    const { data } = await api.get(`/jobs/${jobId}`);
    if (data.status === "completed") { response.data = data.result; return response; }
    if (data.status === "failed" || data.status === "cancelled") {
      throw new Error(data.error?.message || "Processing was cancelled.");
    }
  }
  throw new Error(`Processing continues in the cloud. Job: ${jobId}`);
});

api.interceptors.response.use((response) => {
  const method = (response.config.method || "get").toLowerCase();
  const endpoint = response.config.url || "";
  if (method === "post") {
    if (endpoint.includes("/videos/process")) trackFeatureUse("youtube");
    else if (endpoint.includes("/instagram/process")) trackFeatureUse("instagram");
    else if (endpoint.includes("/chat")) trackFeatureUse("ask_ai");
  }
  return response;
});

export interface VideoMetadata {
  video_id: string;
  title?: string;
  channel?: string;
  duration?: number;
  thumbnail?: string;
  published_at?: string;
}

export interface VideoProcessResponse {
  video_id: string;
  metadata: VideoMetadata;
  summary?: string;
  key_topics: string[];
  chunks_indexed: number;
  processed_at: string;
}

export interface SearchHit {
  score: number;
  text: string;
  source_id: string;
  source_type: string;
  title?: string;
  summary?: string;
  thumbnail?: string;
  duration?: number;
  author?: string;
  created_at?: string;
  chunks?: number;
  entities?: string[];
  tags?: string[];
  url?: string;
}

export interface SearchResponse {
  query: string;
  hits: SearchHit[];
  search_time_ms?: number;
  chunks_searched?: number;
  sources_searched?: number;
}

export interface Citation {
  source_id: string;
  source_type: string;
  title?: string;
  snippet: string;
  url?: string;
  thumbnail?: string;
  score?: number;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface ChatResponse {
  conversation_id?: string;
  question: string;
  answer: string;
  citations: Citation[];
  related_sources?: SearchHit[];
  search_time_ms?: number;
  chunks_searched?: number;
  sources_searched?: number;
}

export type ChatAction = "explain" | "notes" | "flashcards" | "simplify" | "compare";

export const runChatAction = (payload: {
  action: ChatAction;
  question: string;
  answer: string;
  conversation_id?: string;
  source_ids?: string[];
  citations?: Citation[];
  related_sources?: SearchHit[];
}) => api.post<ChatResponse>("/chat/action", payload).then((response) => response.data);

export interface SourceItem {
  source_id: string;
  source_type: string;
  title?: string;
  channel?: string;
  thumbnail?: string;
  summary?: string;
  key_topics: string[];
  chunks_indexed: number;
  created_at: string;
  url?: string;
  file_path?: string;
  file_name?: string;
  file_size?: number;
  mime_type?: string;
  page_count?: number;
}

export interface RecentQuery {
  text: string;
  created_at: string;
}

export interface Stats {
  total_files_stored: number;
  total_storage_bytes: number;
  indexed_chunks: number;
  total_sources: number;
  sources_by_type: Record<string, number>;
  vector_store: string;
  recent_sources: SourceItem[];
  recent_searches: RecentQuery[];
  recent_questions: RecentQuery[];
  knowledge_growth: { date: string; name: string; chunks: number }[];
}

export const processVideo = (url: string) =>
  api.post<VideoProcessResponse>("/videos/process", { url }).then((r) => r.data);

export const processInstagram = (url: string) =>
  api.post<SourceItem>("/instagram/process", { url }).then((r) => r.data);

export const processWeb = (url: string) =>
  api.post<SourceItem>("/web/process", { url }).then((r) => r.data);

const uploadFile = (path: string, file: File) => {
  const form = new FormData();
  form.append("file", file);
  return api
    .post<SourceItem>(path, form, {
      headers: { "Content-Type": "multipart/form-data" },
    })
    .then((r) => r.data);
};

export const processPdf = (file: File) => uploadFile("/pdf/process", file);
export const processDocument = (file: File) =>
  uploadFile("/documents/process", file);
export const processAudio = (file: File) => uploadFile("/audio/process", file);

export const semanticSearch = (
  query: string,
  sourceType?: string,
  topK?: number
) =>
  api
    .post<SearchResponse>("/search", {
      query,
      source_type: sourceType,
      top_k: topK ?? useAppStore.getState().settings.topK,
    })
    .then((r) => r.data);

export const askChat = (
  question: string,
  sourceType?: string,
  sourceId?: string,
  history?: ChatMessage[],
  topK?: number,
  conversationId?: string
) =>
  api
    .post<ChatResponse>("/chat", {
      question,
      source_type: sourceType || undefined,
      source_id: sourceId || undefined,
      history: (history || []).slice(-40),
      conversation_id: conversationId,
      top_k: topK ?? useAppStore.getState().settings.topK,
    })
    .then((r) => r.data);

export const SOURCE_TYPES = [
  "",
  "youtube",
  "instagram",
  "pdf",
  "document",
  "audio",
  "web",
] as const;

export interface HealthStatus {
  status: string;
  app: string;
  environment: string;
  version: string;
}

export interface DetailedHealth {
  status: string;
  app: string;
  environment: string;
  version: string;
  llm_model: string;
  embedding_model: string;
  collection: string;
  checks: Record<string, string>;
}

export const getStats = () =>
  api.get<Stats>("/stats").then((r) => r.data);

export const getHealth = () =>
  api.get<HealthStatus>("/health").then((r) => r.data);

export const getDetailedHealth = () =>
  api.get<DetailedHealth>("/health/detailed").then((r) => r.data);

export const listSources = (sourceType?: string, page: number = 1, pageSize: number = 20) =>
  api
    .get<{ items: SourceItem[]; total: number; page: number; page_size: number; total_pages: number }>(
      "/sources",
      {
        params: {
          ...(sourceType ? { source_type: sourceType } : {}),
          page,
          page_size: pageSize,
        },
      }
    )
    .then((r) => r.data);

export interface GraphNode {
  id: string;
  label: string;
  count: number;
}

export interface GraphEdge {
  source: string;
  target: string;
  label: string;
  source_id: string;
  source_type: string;
  title?: string;
}

export const getGraph = () =>
  api
    .get<{ nodes: GraphNode[]; edges: GraphEdge[] }>("/graph")
    .then((r) => r.data);

export interface GraphRebuildResult {
  sources_seen: number;
  sources_rebuilt: number;
  sources_without_text: number;
  relationships: number;
  failures: { source_id: string; reason: string }[];
}

export const rebuildGraph = () =>
  api.post<GraphRebuildResult>("/graph/rebuild").then((r) => r.data);

export interface TimelineItem {
  source_id: string;
  source_type: string;
  title?: string;
  created_at: string;
}

export interface TimelineGroup {
  label: string;
  items: TimelineItem[];
}

export const getTimeline = () =>
  api.get<{ groups: TimelineGroup[] }>("/timeline").then((r) => r.data);

export interface CompareResult {
  analysis: string;
  source_a: string;
  source_b: string;
}

export const compareSources = (sourceIdA: string, sourceIdB: string) =>
  api
    .post<CompareResult>("/compare", {
      source_id_a: sourceIdA,
      source_id_b: sourceIdB,
    })
    .then((r) => r.data);

export interface Note {
  id: string;
  title: string;
  body: string;
  created_at: string;
}

export const listNotes = () =>
  api.get<Note[]>("/notes").then((r) => r.data);

export const createNote = (title: string, body: string) =>
  api.post<Note>("/notes", { title, body }).then((r) => r.data);

export const deleteNote = (id: string) =>
  api.delete<{ deleted: string }>(`/notes/${id}`).then((r) => r.data);

export const deleteSource = (sourceId: string) =>
  api.delete<{ deleted: string; message: string }>(`/sources/${sourceId}`).then((r) => r.data);

export const downloadSource = async (sourceId: string, fileName?: string) => {
  if (cloudMode) {
    const { data } = await api.get(`/sources/${encodeURIComponent(sourceId)}/link`);
    window.open(data.url, "_blank", "noopener,noreferrer");
    return;
  }
  const { data } = await api.get(`/sources/${encodeURIComponent(sourceId)}/download`, { responseType: "blob" });
  const url = URL.createObjectURL(data);
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName || "download";
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
};
