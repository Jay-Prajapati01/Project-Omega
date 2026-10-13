// Read-only MindMesh capacity workload. Refuses to start without an explicit
// staging target acknowledgement and enough distinct staging user tokens.
// It does not submit jobs, upload content, call AI providers, or change data.
import http from "k6/http";
import { check, sleep } from "k6";

const API_BASE_URL = (__ENV.API_BASE_URL || "").replace(/\/$/, "");
const WEB_BASE_URL = (__ENV.WEB_BASE_URL || "").replace(/\/$/, "");
const PEAK_VUS = Number(__ENV.PEAK_VUS || "100");
const P95_LIMIT_MS = Number(__ENV.P95_LIMIT_MS || "500");
const MAX_ERROR_RATE = Number(__ENV.MAX_ERROR_RATE || "0.01");
const CONFIRMATION = "I_HAVE_VERIFIED_THIS_IS_STAGING";

if (__ENV.TARGET_ENV !== "staging" || __ENV.STAGING_CONFIRMATION !== CONFIRMATION) {
  throw new Error("Refusing to run: set TARGET_ENV=staging and verify the target with STAGING_CONFIRMATION=I_HAVE_VERIFIED_THIS_IS_STAGING.");
}
if (!API_BASE_URL || !WEB_BASE_URL || !Number.isInteger(PEAK_VUS) || PEAK_VUS < 50) {
  throw new Error("Set API_BASE_URL, WEB_BASE_URL, and PEAK_VUS to an integer of at least 50.");
}
if ([API_BASE_URL, WEB_BASE_URL].some((url) => {
  try { return new URL(url).protocol !== "https:"; } catch { return true; }
})) {
  throw new Error("API_BASE_URL and WEB_BASE_URL must be valid HTTPS staging URLs.");
}
if (!Number.isFinite(P95_LIMIT_MS) || P95_LIMIT_MS <= 0 || !Number.isFinite(MAX_ERROR_RATE) || MAX_ERROR_RATE <= 0 || MAX_ERROR_RATE >= 1) {
  throw new Error("P95_LIMIT_MS must be positive and MAX_ERROR_RATE must be between 0 and 1.");
}
if (!__ENV.AUTH_TOKENS_FILE) {
  throw new Error("Set AUTH_TOKENS_FILE to a local, uncommitted file with one current staging access token per line.");
}

const TOKENS = open(__ENV.AUTH_TOKENS_FILE)
  .split(/\r?\n/)
  .map((token) => token.trim())
  .filter(Boolean);
if (TOKENS.length < PEAK_VUS) {
  throw new Error(`Need at least PEAK_VUS (${PEAK_VUS}) distinct staging access tokens; found ${TOKENS.length}.`);
}
if (new Set(TOKENS).size < PEAK_VUS) {
  throw new Error(`Need ${PEAK_VUS} distinct staging tokens so per-user rate limits remain realistic.`);
}

export const options = {
  stages: [
    { duration: "1m", target: 20 },
    { duration: "2m", target: 20 },
    { duration: "1m", target: 50 },
    { duration: "2m", target: 50 },
    { duration: "1m", target: PEAK_VUS },
    { duration: "2m", target: PEAK_VUS },
    { duration: "1m", target: 0 },
  ],
  thresholds: {
    http_req_duration: [`p(95)<${P95_LIMIT_MS}`],
    http_req_failed: [`rate<${MAX_ERROR_RATE}`],
  },
};

function expectOk(response, name) {
  check(response, { [`${name} returns HTTP 200`]: (r) => r.status === 200 });
}

export default function () {
  const token = TOKENS[(__VU - 1) % TOKENS.length];
  const auth = { headers: { Authorization: `Bearer ${token}` } };

  expectOk(http.get(`${WEB_BASE_URL}/`, { tags: { name: "web_home" } }), "web home");
  expectOk(http.get(`${API_BASE_URL}/api/health`, { tags: { name: "api_health" } }), "API health");
  expectOk(http.get(`${API_BASE_URL}/api/sources?page=1&page_size=20`, { ...auth, tags: { name: "sources_list" } }), "sources list");
  expectOk(http.get(`${API_BASE_URL}/api/notes`, { ...auth, tags: { name: "notes_list" } }), "notes list");
  expectOk(http.get(`${API_BASE_URL}/api/graph`, { ...auth, tags: { name: "graph_read" } }), "graph read");
  expectOk(http.get(`${API_BASE_URL}/api/stats`, { ...auth, tags: { name: "stats_read" } }), "stats read");
  sleep(4);
}
