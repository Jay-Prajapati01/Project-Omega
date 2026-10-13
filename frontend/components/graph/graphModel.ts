import type { GraphEdge, GraphNode } from "@/lib/api";

export const SOURCE_COLORS: Record<string, string> = {
  youtube: "#FF5C00",
  instagram: "#FF5C00",
  pdf: "#E14E00",
  document: "#E14E00",
  audio: "#E14E00",
  web: "#B96A00",
};

export const SOURCE_LABELS: Record<string, string> = {
  youtube: "YouTube",
  instagram: "Instagram",
  pdf: "PDF",
  document: "Document",
  audio: "Audio",
  web: "Web",
};

export const BRAND_COLOR = "#FF5C00";

export const sourceColor = (type?: string): string =>
  (type && SOURCE_COLORS[type]) || BRAND_COLOR;

/**
 * Make extracted labels human-readable: markdown links/images and raw URLs
 * often leak into concept labels (e.g. `[![](https://x)](https://x "Title")`).
 */
export function cleanLabel(raw: string): string {
  if (!raw) return "Untitled concept";
  let s = raw;
  // Images: ![alt](url) → alt text
  s = s.replace(/!\[([^\]]*)\]\([^)]*\)/g, "$1");
  // Links: [text](url "title") → text, else title, else url without protocol
  s = s.replace(/\[([^\]]*)\]\s*\(([^)]*)\)/g, (_m, text: string, dest: string) => {
    const t = (text ?? "").trim();
    if (t) return t;
    const title = dest.match(/"([^"]+)"/);
    if (title) return title[1];
    const url = dest
      .replace(/"[^"]*"/g, "")
      .trim()
      .split(/\s+/)[0] ?? "";
    return url.replace(/^https?:\/\//, "").replace(/\/+$/, "");
  });
  // Bare URLs → drop protocol and trailing slash
  s = s.replace(/https?:\/\/[^\s)\]]+/g, (m) => m.replace(/^https?:\/\//, "").replace(/\/+$/, ""));
  s = s.replace(/\s+/g, " ").trim();
  return s || "Untitled concept";
}

export interface Incidence {
  edge: GraphEdge;
  otherId: string;
  direction: "out" | "in";
}

export interface Adjacency {
  incident: Map<string, Incidence[]>;
  degree: Map<string, number>;
  dominant: Map<string, string>;
}

export function buildAdjacency(nodes: GraphNode[], edges: GraphEdge[]): Adjacency {
  const incident = new Map<string, Incidence[]>();
  const degree = new Map<string, number>();
  const typeVotes = new Map<string, Map<string, number>>();

  for (const n of nodes) {
    incident.set(n.id, []);
    degree.set(n.id, 0);
  }

  for (const e of edges) {
    const out = incident.get(e.source);
    const inc = incident.get(e.target);
    if (out) {
      out.push({ edge: e, otherId: e.target, direction: "out" });
      degree.set(e.source, (degree.get(e.source) ?? 0) + 1);
      let votes = typeVotes.get(e.source);
      if (!votes) {
        votes = new Map();
        typeVotes.set(e.source, votes);
      }
      votes.set(e.source_type, (votes.get(e.source_type) ?? 0) + 1);
    }
    if (inc) {
      inc.push({ edge: e, otherId: e.source, direction: "in" });
      degree.set(e.target, (degree.get(e.target) ?? 0) + 1);
      let votes = typeVotes.get(e.target);
      if (!votes) {
        votes = new Map();
        typeVotes.set(e.target, votes);
      }
      votes.set(e.source_type, (votes.get(e.source_type) ?? 0) + 1);
    }
  }

  const dominant = new Map<string, string>();
  for (const [id, votes] of typeVotes) {
    let best = "";
    let bestCount = -1;
    for (const [type, count] of votes) {
      if (count > bestCount || (count === bestCount && type < best)) {
        best = type;
        bestCount = count;
      }
    }
    dominant.set(id, best);
  }

  return { incident, degree, dominant };
}

/** Rough half-width of a rendered chip, used to keep nodes from overlapping. */
export function estimateRadius(label: string, degree: number): number {
  const len = cleanLabel(label).length;
  const shown = len > 34 ? 34 : len;
  const width = 44 + shown * 7.8;
  return Math.min(80, Math.max(22, width / 2)) + Math.min(degree, 8) * 2.5;
}

function mulberry32(seed: number) {
  let a = seed >>> 0;
  return () => {
    a += 0x6d2b79f5;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/**
 * Deterministic Fruchterman-Reingold force layout.
 * Repulsion between every pair (scaled by node radius), springs along edges,
 * gentle gravity toward the center, cooling schedule so it converges.
 */
export function runForceLayout(
  ids: string[],
  edges: { source: string; target: string }[],
  radii: Record<string, number>,
): Record<string, { x: number; y: number }> {
  const n = ids.length;
  if (n === 0) return {};
  if (n === 1) return { [ids[0]]: { x: 0, y: 0 } };

  const index = new Map(ids.map((id, i) => [id, i]));
  const springs: [number, number][] = [];
  for (const e of edges) {
    const a = index.get(e.source);
    const b = index.get(e.target);
    if (a === undefined || b === undefined || a === b) continue;
    springs.push([a, b]);
  }

  const rand = mulberry32(0x9e3779b9 ^ (n * 2654435761));
  const px = new Float64Array(n);
  const py = new Float64Array(n);
  const fx = new Float64Array(n);
  const fy = new Float64Array(n);
  const r = new Float64Array(n);
  for (let i = 0; i < n; i++) r[i] = radii[ids[i]] ?? 24;

  const seedRadius = Math.max(140, Math.sqrt(n) * 36);
  for (let i = 0; i < n; i++) {
    const angle = (i / n) * Math.PI * 2;
    px[i] = seedRadius * Math.cos(angle) + (rand() - 0.5) * 40;
    py[i] = seedRadius * Math.sin(angle) + (rand() - 0.5) * 40;
  }

  const area = 2700 * 1800;
  const k = Math.max(70, Math.sqrt(area / n));
  const initialTemp = 1.8 * k;
  const iterations = 400;
  const gravity = 3.0;

  for (let it = 0; it < iterations; it++) {
    const temp = initialTemp * Math.pow(0.965, it);
    fx.fill(0);
    fy.fill(0);

    // Pairwise repulsion (with hard separation at overlap distance)
    for (let i = 0; i < n; i++) {
      for (let j = i + 1; j < n; j++) {
        let dx = px[i] - px[j];
        let dy = py[i] - py[j];
        let distSq = dx * dx + dy * dy;
        if (distSq < 0.01) {
          dx = (rand() - 0.5) * 2;
          dy = (rand() - 0.5) * 2;
          distSq = dx * dx + dy * dy;
        }
        const dist = Math.sqrt(distSq);
        const minDist = r[i] + r[j] + 22;
        const force = dist < minDist ? (minDist - dist) * 4.5 : (k * k) / dist;
        const ux = dx / dist;
        const uy = dy / dist;
        fx[i] += ux * force;
        fy[i] += uy * force;
        fx[j] -= ux * force;
        fy[j] -= uy * force;
      }
    }

    // Springs along edges
    for (const [a, b] of springs) {
      const dx = px[a] - px[b];
      const dy = py[a] - py[b];
      const dist = Math.max(0.5, Math.sqrt(dx * dx + dy * dy));
      const force = (dist * dist) / k;
      const ux = dx / dist;
      const uy = dy / dist;
      fx[a] -= ux * force;
      fy[a] -= uy * force;
      fx[b] += ux * force;
      fy[b] += uy * force;
    }

    // Gravity keeps disconnected pieces around the center
    for (let i = 0; i < n; i++) {
      fx[i] -= px[i] * gravity;
      fy[i] -= py[i] * gravity;
    }

    // Move each node at most `temp` along its net force
    for (let i = 0; i < n; i++) {
      const mag = Math.sqrt(fx[i] * fx[i] + fy[i] * fy[i]);
      if (mag < 1e-6) continue;
      const step = Math.min(mag, temp);
      px[i] += (fx[i] / mag) * step;
      py[i] += (fy[i] / mag) * step;
    }
  }

  // Center on origin
  let cx = 0;
  let cy = 0;
  for (let i = 0; i < n; i++) {
    cx += px[i];
    cy += py[i];
  }
  cx /= n;
  cy /= n;

  // Contain within a target box (only shrink) so fit-to-view lands at a
  // usable zoom even for much larger graphs.
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  for (let i = 0; i < n; i++) {
    minX = Math.min(minX, px[i]);
    maxX = Math.max(maxX, px[i]);
    minY = Math.min(minY, py[i]);
    maxY = Math.max(maxY, py[i]);
  }
  const scale = Math.min(1, 2800 / Math.max(1, maxX - minX), 2500 / Math.max(1, maxY - minY));

  // Stretch horizontally so the graph fills a wide viewport rectangle. This
  // only widens horizontal gaps between chips (never causes overlap), and the
  // fit zoom stays bound by the height cap, so it simply uses the empty side
  // space of a wide canvas.
  const w = (maxX - minX) * scale;
  const h = (maxY - minY) * scale;
  const stretchX = w > 0 && h > 0 ? Math.min(1.9, Math.max(1, 1.78 / (w / h))) : 1;

  const out: Record<string, { x: number; y: number }> = {};
  for (let i = 0; i < n; i++) {
    out[ids[i]] = {
      x: Math.round((px[i] - cx) * scale * stretchX * 10) / 10,
      y: Math.round((py[i] - cy) * scale * 10) / 10,
    };
  }
  return out;
}
