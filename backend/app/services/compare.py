"""Cross-source intelligence: compare two indexed sources with the LLM."""
from __future__ import annotations

from app.services import llm, vectorstore

_COMPARE_SYS = (
    "You are MindMesh's analytical engine. You compare two sources of "
    "information objectively, using ONLY the provided content."
)


def _assemble(source_id: str, max_chars: int = 4000) -> str:
    chunks = vectorstore.get_chunks_by_source(source_id)
    text = "\n".join(c.get("text", "") for c in chunks)
    return text[:max_chars]


async def compare(source_id_a: str, source_id_b: str) -> dict:
    """Compare two sources and return a structured analysis."""
    text_a = _assemble(source_id_a)
    text_b = _assemble(source_id_b)

    if not text_a or not text_b:
        return {
            "analysis": "One or both sources have no indexed content.",
            "source_a": source_id_a,
            "source_b": source_id_b,
        }

    prompt = (
        "Compare SOURCE A and SOURCE B. Provide a markdown analysis with these "
        "sections: ## Similarities, ## Differences, ## Contradictions, "
        "## Combined takeaway. Use only the given content.\n\n"
        f"SOURCE A:\n{text_a}\n\n---\n\nSOURCE B:\n{text_b}"
    )
    analysis = await llm.generate(prompt, system=_COMPARE_SYS)
    return {
        "analysis": analysis,
        "source_a": source_id_a,
        "source_b": source_id_b,
    }
