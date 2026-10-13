"""Flexible, tenant-scoped hybrid retrieval shared by Search and Ask AI.

Vector similarity is useful for paraphrases, but is not a probability and by
itself will always return nearest neighbours. This module combines semantic
similarity with lexical coverage, title matches, common acronym expansions,
and query-aware abstention for short entity lookups.
"""
from __future__ import annotations

import re
from collections.abc import Iterable

from app.core.config import get_settings
from app.services import embeddings, note_search, vectorstore

_TOKEN_RE = re.compile(r"[a-z0-9]+|[\u0900-\u097f]+", re.IGNORECASE)
_STOP_WORDS = {
    "a", "about", "after", "all", "an", "and", "any", "are", "as", "at",
    "be", "because", "before", "between", "by", "can", "content", "did",
    "do", "does", "for", "from", "give", "have", "i", "in", "is", "it",
    "me", "my", "of", "on", "or", "please", "related", "show", "tell",
    "that", "the", "their", "these", "this", "to", "what", "which", "who",
    "with", "would", "you", "your", "video", "videos", "reel", "reels",
    "post", "posts", "saved", "save", "find", "about",
}

# Small, explicit equivalence groups cover common shorthand while semantic
# embeddings remain free to retrieve broader paraphrases.
_ALIAS_GROUPS = (
    ("ai", "artificial intelligence"),
    ("ml", "machine learning"),
    ("llm", "large language model", "large language models"),
    ("genai", "generative ai", "generative artificial intelligence"),
    ("agent", "agents", "agentic", "autonomous agent", "autonomous agents"),
)
_ALIAS_LOOKUP: dict[str, tuple[str, ...]] = {}
for _group in _ALIAS_GROUPS:
    for _term in _group:
        _ALIAS_LOOKUP[_term] = tuple(term for term in _group if term != _term)
_ALIAS_WORDS = {word for phrase in _ALIAS_LOOKUP for word in phrase.split()}


def _tokens(text: str) -> list[str]:
    return [token.casefold() for token in _TOKEN_RE.findall(text)]


def _query_variants(query: str) -> list[str]:
    variants = [query]
    folded = query.casefold()
    for group in _ALIAS_GROUPS:
        for term in group:
            if not re.search(rf"(?<!\w){re.escape(term)}(?!\w)", folded):
                continue
            for alias in group:
                if alias == term:
                    continue
                variant = re.sub(
                    rf"(?<!\w){re.escape(term)}(?!\w)", alias, query,
                    flags=re.IGNORECASE,
                )
                if variant.casefold() not in {v.casefold() for v in variants}:
                    variants.append(variant)
            break
    return variants[:5]


def _term_groups(query: str) -> list[set[str]]:
    groups: list[set[str]] = []
    tokens = _tokens(query)
    index = 0
    while index < len(tokens):
        # Keep multiword aliases (for example "artificial intelligence") as
        # one concept so matching either form satisfies the same query intent.
        phrase = " ".join(tokens[index:index + 2])
        if phrase in _ALIAS_LOOKUP:
            groups.append({phrase, *_ALIAS_LOOKUP[phrase]})
            index += 2
            continue
        token = tokens[index]
        if token not in _STOP_WORDS and len(token) > 1:
            groups.append({token, *_ALIAS_LOOKUP.get(token, ())})
        index += 1
    return groups


def _bare_name_query(query: str) -> list[str] | None:
    """Detect short title-cased name lookups (Jay, Jay Prajapati).

    These queries need a literal name occurrence; a vector neighbour alone is
    not evidence that a saved item mentions that person.
    """
    words = re.findall(r"[A-Za-z][A-Za-z'-]*", query.strip())
    if not 1 <= len(words) <= 3:
        return None
    if any(not word[:1].isupper() or not word[1:].islower() for word in words):
        return None
    normalized = [word.casefold() for word in words]
    if " ".join(normalized) in _ALIAS_LOOKUP:
        return None
    if any(" " in alias for word in normalized for alias in _ALIAS_LOOKUP.get(word, ())):
        return None
    return normalized


def _named_terms_in_question(query: str) -> list[str]:
    """Find likely proper names inside a natural-language question."""
    words = re.findall(r"\b[A-Z][a-z]{2,}\b", query)
    ignored = {
        "What", "Which", "Who", "When", "Where", "Why", "How", "Can",
        "Could", "Would", "Please", "Find", "Show", "Tell", "List", "Give",
        "Does", "Did", "Are", "Is", "Have", "Has", "The", "My", "Your",
        "YouTube", "Instagram", "Stored", "Videos", "Reels", "Content",
        "ChatGPT", "Grok",
    }
    return [word.casefold() for word in words if word not in ignored and word.casefold() not in _ALIAS_WORDS]


def _lexical_features(query: str, hit: dict) -> tuple[float, float, bool]:
    text = str(hit.get("text") or "")
    title = str(hit.get("title") or "")
    content = " ".join((title, text)).casefold()
    title_folded = title.casefold()
    groups = _term_groups(query)
    if not groups:
        return 0.0, 0.0, False

    def matches(group: set[str], haystack: str) -> bool:
        return any(
            re.search(rf"(?<!\w){re.escape(term)}(?!\w)", haystack)
            for term in group
        )

    matched = [group for group in groups if matches(group, content)]
    title_matches = [group for group in groups if matches(group, title_folded)]
    coverage = len(matched) / len(groups)
    title_coverage = len(title_matches) / len(groups)
    phrase = " ".join(_tokens(query))
    phrase_match = bool(phrase and phrase in " ".join(_tokens(title + " " + text)))
    return coverage, title_coverage, phrase_match


def _candidate_key(hit: dict) -> tuple[str, str]:
    source_id = str(hit.get("source_id") or "")
    chunk_id = str(hit.get("chunk_index", ""))
    if not chunk_id:
        chunk_id = str(hash(str(hit.get("text") or "")))
    return source_id, chunk_id


def _rerank(query: str, candidates: Iterable[dict]) -> list[dict]:
    name_words = _bare_name_query(query) or _named_terms_in_question(query)
    ranked: list[dict] = []
    for original in candidates:
        hit = dict(original)
        semantic = max(0.0, min(1.0, float(hit.get("score") or 0.0)))
        coverage, title_coverage, phrase_match = _lexical_features(query, hit)
        searchable_text = f"{hit.get('title') or ''} {hit.get('text') or ''}".casefold()

        # A short person-name lookup must actually occur in the saved source.
        # Longer questions keep semantic flexibility and only receive lexical
        # boosts/penalties, rather than being forced into exact-word search.
        if name_words and not all(
            re.search(rf"(?<!\w){re.escape(word)}(?!\w)", searchable_text)
            for word in name_words
        ):
            continue

        score = 0.68 * semantic + 0.25 * coverage + 0.05 * title_coverage + 0.02 * phrase_match
        score = round(max(0.0, min(1.0, score)), 4)

        # Adaptive abstention: exact/related terms can rescue moderate vector
        # scores, while a semantic-only candidate must be clearly stronger.
        # For very short lookups, require lexical evidence or a strong vector.
        if name_words is None:
            baseline = max(0.25, min(0.7, get_settings().chat_min_score))
            minimum = max(baseline, 0.34 if len(_term_groups(query)) >= 2 else 0.39)
            if coverage == 0 and semantic < 0.62:
                continue
            if score < minimum:
                continue
        hit["score"] = score
        hit["semantic_score"] = round(semantic, 4)
        hit["term_coverage"] = round(coverage, 4)
        ranked.append(hit)
    ranked.sort(key=lambda item: item["score"], reverse=True)
    return ranked


async def search(query: str, limit: int = 30, source_type: str | None = None,
                 source_id: str | None = None, include_notes: bool = True) -> tuple[list[dict], int]:
    """Return reranked relevant chunks and the number of raw candidates scanned."""
    candidates: dict[tuple[str, str], dict] = {}
    scan_limit = min(max(limit * 5, 30), 150)
    for variant in _query_variants(query):
        vector = await embeddings.embed_text(variant, purpose="query")
        for hit in vectorstore.search(vector, scan_limit, source_type=source_type, source_id=source_id):
            key = _candidate_key(hit)
            previous = candidates.get(key)
            if previous is None or float(hit.get("score") or 0) > float(previous.get("score") or 0):
                candidates[key] = hit
    raw_count = len(candidates)

    if include_notes and not source_id:
        for hit in note_search.note_hits(query, source_type):
            candidates[_candidate_key(hit)] = hit

    return _rerank(query, candidates.values())[:limit], raw_count
