"""Knowledge graph: extract entities/relations and persist a graph.

During ingestion, `extract_relations` asks the LLM for (subject, relation,
object) triples describing the key concepts in a piece of text. These are
stored as nodes and edges in a JSON-backed graph store, each edge linked to
the source it came from. `get_graph` returns nodes + edges for visualization.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from app.core.logging import get_logger
from app.core.tenant import cloud, data_directory
from app.services import cloud_db, llm

logger = get_logger(__name__)
_lock = cloud_db.StoreLock()

_EXTRACT_SYS = (
    "You extract knowledge graph triples. Given text, return the most "
    "important concepts and how they relate."
)

_MAX_NODES = 500
_MAX_EDGES = 1000
_FALLBACK_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "from",
    "how", "in", "into", "is", "it", "its", "of", "on", "or", "that", "the",
    "their", "this", "to", "using", "was", "were", "with", "your", "you",
    "my", "our", "they", "them", "who", "what", "when", "where", "why", "will",
    "can", "could", "should", "would", "have", "has", "had", "do", "does", "did",
    "how", "video", "videos", "content", "author", "discusses", "mentions", "shows",
    "explains", "provides", "includes", "using", "steps", "process", "various", "multiple",
    "free", "own", "minutes", "paid", "plan", "new", "more", "also", "such", "like",
    "link", "links", "further", "information", "reference", "references", "share", "sharing",
    "original", "audio", "video", "videos", "content", "skill", "skills",
}


def _path() -> Path:
    data_dir = data_directory()
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "graph.json"


def _load() -> dict:
    if cloud():
        return cloud_db.load("graph", {"nodes": {}, "edges": []})
    path = _path()
    if not path.exists():
        return {"nodes": {}, "edges": []}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {"nodes": {}, "edges": []}


def _save(data: dict) -> None:
    if cloud():
        cloud_db.save("graph", data)
        return
    path = _path()
    # Atomic write: a crash mid-write must never truncate graph.json.
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, default=str, indent=2))
    tmp.replace(path)


def remove_source(source_id: str) -> None:
    """Drop all nodes/edges that came from a deleted source."""
    with _lock:
        data = _load()
        data["edges"] = [e for e in data["edges"] if e.get("source_id") != source_id]
        data["nodes"] = _nodes_from_edges(data["edges"])
        _save(data)


def _nodes_from_edges(edges: list[dict]) -> dict:
    """Recompute concept counts from provenance-bearing edges."""
    nodes: dict[str, dict] = {}
    for edge in edges:
        for key in (edge["source"], edge["target"]):
            nodes.setdefault(key, {"label": key, "count": 0})["count"] += 1
    return nodes


async def extract_relations(text: str) -> list[dict]:
    """Ask the LLM for up to ~10 (subject, relation, object) triples."""
    excerpt = text[:6000]
    prompt = (
        "Extract up to 10 knowledge triples from the text. Respond ONLY as "
        'JSON: {"triples": [{"subject": str, "relation": str, "object": str}]}.'
        f"\n\nTEXT:\n{excerpt}"
    )
    raw = await llm.generate(prompt, system=_EXTRACT_SYS)
    try:
        start, end = raw.find("{"), raw.rfind("}")
        data = json.loads(raw[start : end + 1])
        triples = data.get("triples", [])
        return [
            t
            for t in triples
            if t.get("subject") and t.get("relation") and t.get("object")
        ]
    except (ValueError, json.JSONDecodeError):
        logger.warning("Failed to parse graph triples")
        return []


def add_triples(
    triples: list[dict],
    source_id: str,
    source_type: str,
    title: str | None = None,
) -> int:
    """Store one source's current triples (idempotent despite legacy name)."""
    return replace_triples(triples, source_id, source_type, title)


def _prune_graph(data: dict) -> dict:
    """Remove least important nodes/edges to stay within limits."""
    # Sort nodes by count (importance) and keep top N
    sorted_nodes = sorted(
        data["nodes"].items(),
        key=lambda x: x[1].get("count", 0),
        reverse=True,
    )
    kept_keys = {k for k, _ in sorted_nodes[:_MAX_NODES]}
    
    # Filter nodes
    data["nodes"] = {k: v for k, v in data["nodes"].items() if k in kept_keys}
    
    # Filter edges to only include kept nodes
    data["edges"] = [
        e for e in data["edges"]
        if e["source"] in kept_keys and e["target"] in kept_keys
    ][:_MAX_EDGES]
    
    logger.info("Pruned graph to %d nodes, %d edges", len(data["nodes"]), len(data["edges"]))
    return data


def get_graph() -> dict:
    """Return the graph as {nodes: [...], edges: [...]} for the frontend."""
    data = _load()
    nodes = [
        {"id": key, "label": node["label"], "count": node["count"]}
        for key, node in data["nodes"].items()
    ]
    return {"nodes": nodes, "edges": data["edges"]}


def replace_triples(triples, source_id, source_type, title=None):
    """Atomically replace one source's edges and recompute node counts on retries."""
    with _lock:
        data = _load()
        edges = [e for e in data["edges"] if e.get("source_id") != source_id]
        unique = {(t["subject"].strip().lower(), t["object"].strip().lower(), t["relation"].strip()) for t in triples}
        edges.extend({"source": a, "target": b, "label": relation, "source_id": source_id,
                      "source_type": source_type, "title": title} for a, b, relation in sorted(unique))
        nodes = _nodes_from_edges(edges)
        _save(_prune_graph({"nodes": nodes, "edges": edges}))
    return len(unique)


def _summary_fallback_triples(title: str, summary: str) -> list[dict]:
    """Build conservative source-local links when legacy text has no triples.

    This intentionally uses only phrases present in the saved title/summary;
    it does not invent entities or rely on source/platform defaults.
    """
    title_tokens = re.findall(r"[A-Za-z][A-Za-z0-9.+-]*", title.lower())
    summary_tokens = re.findall(r"[A-Za-z][A-Za-z0-9.+-]*", summary.lower())

    def phrases(tokens: list[str]) -> Counter:
        useful = [
            token for token in tokens
            if token not in _FALLBACK_STOPWORDS
            and len(token) > 2
            and not any(char.isdigit() for char in token)
            and "@" not in token
        ]
        found: Counter = Counter()
        for size in (2, 3):
            for start in range(len(useful) - size + 1):
                phrase = " ".join(useful[start : start + size])
                if len(phrase) <= 48:
                    found[phrase] += 1
        return found

    title_phrases = phrases(title_tokens)
    summary_phrases = phrases(summary_tokens)
    candidates = set(title_phrases) | set(summary_phrases)
    # Prefer phrases anchored in the title and repeated in the source summary.
    ranked = sorted(
        candidates,
        key=lambda phrase: (
            4 * title_phrases[phrase] + summary_phrases[phrase],
            len(phrase.split()),
            len(phrase),
        ),
        reverse=True,
    )
    selected = ranked[:6]
    if len(selected) < 2:
        return []
    anchor = selected[0]
    return [
        {"subject": anchor, "relation": "covers", "object": phrase}
        for phrase in selected[1:]
        if phrase != anchor
    ]


async def rebuild_from_saved_sources() -> dict:
    """Re-extract graph relations from each tenant-owned indexed source."""
    from app.services import store, vectorstore

    sources = store.list_sources()
    result = {"sources_seen": len(sources), "sources_rebuilt": 0, "sources_without_text": 0,
              "relationships": 0, "failures": []}
    for item in sources:
        source_id = item.get("source_id")
        source_type = item.get("source_type")
        if not source_id or not source_type:
            result["failures"].append({"source_id": source_id or "unknown", "reason": "Missing source identity or type"})
            continue
        try:
            chunks = vectorstore.get_chunks_by_source(source_id, source_type=source_type)
            text = "\n\n".join(chunk.get("text", "").strip() for chunk in chunks if chunk.get("text", "").strip())
            # Older saved sources may have lost their Qdrant chunks during an
            # earlier ingest, while their durable source metadata still has a
            # useful summary. Use that summary to backfill graph provenance.
            summary = str(item.get("summary") or "").strip()
            fallback_text = "\n".join(
                part for part in (
                    f"Title: {item.get('title', '')}".strip(),
                    f"Summary: {summary}" if summary else "",
                ) if part
            )
            if not text and not fallback_text:
                # No indexed content or durable summary remains, so remove
                # stale graph links instead of inventing concepts.
                result["sources_without_text"] += 1
                result["relationships"] += replace_triples([], source_id, source_type, item.get("title"))
                result["sources_rebuilt"] += 1
                continue
            triples = await extract_relations(text or fallback_text)
            if not triples and fallback_text and text:
                # Chunk text can be noisy or too fragmented for extraction;
                # retry against the source-level summary before clearing links.
                triples = await extract_relations(fallback_text)
            existing_count = sum(
                1 for edge in _load().get("edges", [])
                if edge.get("source_id") == source_id
            )
            if triples:
                count = replace_triples(triples, source_id, source_type, item.get("title"))
            elif existing_count:
                # A model returning no parseable triples is not evidence that
                # the source has no knowledge. Keep previously useful links.
                count = existing_count
            else:
                fallback_triples = _summary_fallback_triples(
                    str(item.get("title") or ""), summary
                )
                count = replace_triples(
                    fallback_triples, source_id, source_type, item.get("title")
                )
            result["relationships"] += count
            result["sources_rebuilt"] += 1
        except Exception as exc:  # noqa: BLE001
            logger.exception("Graph rebuild failed for source %s", source_id)
            # A vector-store read can fail for an individual legacy record.
            # Recover that source from its durable summary so the rest of the
            # graph remains source-linked and the item is still discoverable.
            fallback = _summary_fallback_triples(
                str(item.get("title") or ""), str(item.get("summary") or "")
            )
            if fallback:
                result["relationships"] += replace_triples(
                    fallback, source_id, source_type, item.get("title")
                )
                result["sources_rebuilt"] += 1
                continue
            result["failures"].append({"source_id": source_id, "reason": type(exc).__name__})

    # A legacy source can yield parseable but empty provider output without
    # raising an exception. Make a second pass for sources still unconnected,
    # using only their persisted title/summary as a deterministic fallback.
    current_edges = _load().get("edges", [])
    for item in sources:
        source_id = item.get("source_id")
        if not source_id or any(edge.get("source_id") == source_id for edge in current_edges):
            continue
        fallback = _summary_fallback_triples(
            str(item.get("title") or ""), str(item.get("summary") or "")
        )
        if not fallback:
            continue
        count = replace_triples(
            fallback, source_id, item.get("source_type", ""), item.get("title")
        )
        result["relationships"] += count
        current_edges = _load().get("edges", [])
    return result
