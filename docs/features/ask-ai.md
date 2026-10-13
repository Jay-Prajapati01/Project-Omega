# Ask AI

The `/chat` page calls `POST /api/chat`. `backend/app/services/rag.py` retrieves tenant-scoped source chunks and workspace notes through the shared hybrid ranker, assembles grounded context, and asks the selected LLM for an answer. The response includes citations, ranked related sources, and retrieval metrics. Related source cards appear below each answer with thumbnails, a relevance score, and a direct open-source action.

Retrieval combines vector cosine similarity with query-term coverage and title matches. Common shorthand such as AI / artificial intelligence and ML / machine learning is expanded for retrieval, while embeddings still allow broader paraphrases. Short person-name lookups require the name to occur in the saved text, which avoids treating an arbitrary nearest vector neighbor as a match. Longer natural-language questions are not forced into exact-word matching. The displayed score is a ranking signal, not a probability or guarantee of factual correctness.

The former `/search` page redirects to `/chat` and preserves a `q` parameter for old links. Search is no longer a separate navigation destination; Ask AI owns both conversational retrieval and source discovery.

The LLM backend is selected in `backend/app/core/backend_config.py`: Groq when configured, Hugging Face Spaces when configured, otherwise local Ollama. Cloud execution routes through the cloud LLM service. Embeddings are provider-configurable (Ollama or Gemini in the source configuration) and must use a model/dimension compatible with the vector collection.

Conversation history and source references are tenant/user scoped. If no relevant material clears the adaptive relevance checks, the answer pipeline reports that rather than grounding the answer in a different tenant's data.
