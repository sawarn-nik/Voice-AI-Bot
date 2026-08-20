"""
Retriever
=========
High-level interface used by the voice agent and any other consumer.

Design
------
- Embed the query with the same model used at index time.
- Search the vector store with optional category filtering.
- Re-rank results using a simple keyword-boost heuristic to lift exact-match
  records that cosine similarity may have scored slightly lower.
- Return up to top_k results with citations.
- If no result meets the minimum score threshold, return an explicit
  "no-answer" signal so the caller can say "I don't have that information"
  rather than hallucinating.
"""

from __future__ import annotations

from typing import List, Optional

from q2_knowledge_base.schema import KBRecord, RetrievalResult, RetrievalQuery
from q2_knowledge_base.embedder import Embedder, get_vector_store
from shared.config import settings
from shared.utils import logger


class Retriever:
    """
    Main retrieval interface.

    Usage
    -----
        retriever = Retriever()
        results = retriever.search("What is the waiting period for pre-existing conditions?")
        for r in results:
            print(r.record.content, r.score, r.citation)
    """

    def __init__(self):
        self._embedder = Embedder()
        self._store = get_vector_store()
        logger.info("retriever_ready", store=type(self._store).__name__)

    def search(
        self,
        query: str,
        top_k: int = None,
        category_filter: Optional[str] = None,
        min_score: float = None,
    ) -> List[RetrievalResult]:
        """
        Embed query → vector search → re-rank → return results.

        Returns empty list if nothing meets the confidence threshold.
        Callers should treat an empty list as "information not available".
        """
        top_k = top_k or settings.kb_top_k
        min_score = min_score if min_score is not None else 0.45

        q = RetrievalQuery(
            query=query,
            top_k=top_k * 2,  # over-fetch for re-ranking
            category_filter=category_filter,
            min_score=min_score,
        )

        query_vector = self._embedder.embed_one(query)
        raw_results = self._store.search(q, query_vector)

        if not raw_results:
            logger.info("retriever_no_results", query=query[:80])
            return []

        reranked = self._rerank(query, raw_results)
        final = reranked[:top_k]

        logger.info(
            "retriever_results",
            query=query[:80],
            count=len(final),
            top_score=final[0].score if final else 0,
        )
        return final

    def search_grounded(self, query: str, **kwargs) -> tuple[str, List[RetrievalResult]]:
        """
        Convenience method that returns a formatted context string and the
        raw results together, ready to inject into an LLM system prompt.

        Returns
        -------
        (context_text, results)
        """
        results = self.search(query, **kwargs)
        if not results:
            return "No relevant information found in the knowledge base.", []

        parts = []
        for i, r in enumerate(results, 1):
            parts.append(
                f"[{i}] {r.record.title}\n"
                f"Source: {r.citation}\n"
                f"Score: {r.score:.2f}\n"
                f"{r.record.content}"
            )
        context = "\n\n---\n\n".join(parts)
        return context, results

    # ------------------------------------------------------------------
    # Re-ranking
    # ------------------------------------------------------------------

    def _rerank(
        self, query: str, results: List[RetrievalResult]
    ) -> List[RetrievalResult]:
        """
        Simple keyword-boost re-ranker.
        Adds a small bonus (0.05) to records whose content contains query tokens.
        Then sorts descending by boosted score.
        """
        query_tokens = set(query.lower().split())
        boosted = []
        for r in results:
            content_lower = r.record.content.lower()
            overlap = sum(1 for t in query_tokens if t in content_lower)
            boost = min(overlap * 0.01, 0.05)  # cap at +0.05
            adjusted = min(r.score + boost, 1.0)
            boosted.append((adjusted, r))

        boosted.sort(key=lambda x: x[0], reverse=True)
        # Return with original scores (don't mutate) but sorted by boosted score
        return [r for _, r in boosted]
