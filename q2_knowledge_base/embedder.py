"""
Embedding & Indexing
====================
Embeds KB records and upserts them into a vector store.

Vector Store Strategy
---------------------
- Primary:  Pinecone (managed, production-ready, serverless)
- Fallback: Qdrant running locally in Docker (zero-cost dev/test)

The `VectorStore` abstraction lets both share the same interface so the
voice agent retriever never needs to know which backend is active.

Embedding Model
---------------
`text-embedding-3-small` (OpenAI)
- 1536 dimensions, strong multilingual support, cheap (~$0.02/1M tokens)
- Chosen over `ada-002` for better semantic accuracy and lower cost.
"""

from __future__ import annotations

import json
from typing import List, Optional, Dict, Any

import openai
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
)

from q2_knowledge_base.schema import KBRecord, RetrievalResult, RetrievalQuery
from shared.providers import EMBEDDING_DIM as VECTOR_DIM
from shared.config import settings
from shared.utils import logger


# ---------------------------------------------------------------------------
# OpenAI Embedder
# ---------------------------------------------------------------------------

class Embedder:
    """
    Delegates to shared.providers.EmbeddingProvider.
    Primary: GeminiEmbeddingProvider (free, multilingual)
    Fallback: LocalHashEmbeddingProvider (offline)
    """
    def __init__(self):
        from shared.providers import get_embedding_provider
        self._provider = get_embedding_provider()

    def embed(self, texts):
        if not texts:
            return []
        return self._provider.embed(texts)

    def embed_one(self, text):
        return self._provider.embed_one(text)



"""
Qdrant singleton — ensures only one QdrantClient instance exists per process.
This avoids the file lock conflict when multiple parts of the app open the store.
"""

_qdrant_instance = None


def get_qdrant_client():
    """Return the process-wide shared QdrantClient (create once, reuse always)."""
    global _qdrant_instance
    if _qdrant_instance is None:
        import os
        path = getattr(settings, "qdrant_path", "q2_knowledge_base/embeddings")
        if path == ":memory:":
            _qdrant_instance = QdrantClient(":memory:")
        else:
            os.makedirs(path, exist_ok=True)
            _qdrant_instance = QdrantClient(path=path)
        logger.info("qdrant_client_created", path=path)
    return _qdrant_instance


class QdrantVectorStore:
    """
    Local Qdrant store using a process-wide singleton client.
    Safe to instantiate multiple times — always reuses the same underlying connection.
    """

    def __init__(self):
        self._client = get_qdrant_client()
        self.collection = settings.qdrant_collection
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        existing = [c.name for c in self._client.get_collections().collections]
        if self.collection not in existing:
            self._client.create_collection(
                collection_name=self.collection,
                vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
            )
            logger.info("qdrant_collection_created", name=self.collection)

    def upsert(self, records: List[KBRecord], vectors: List[List[float]]) -> None:
        points = []
        for record, vector in zip(records, vectors):
            payload = record.model_dump()
            points.append(
                PointStruct(
                    id=abs(hash(record.record_id)) % (2**63),
                    vector=vector,
                    payload=payload,
                )
            )
        self._client.upsert(collection_name=self.collection, points=points)
        logger.info("qdrant_upserted", count=len(points))

    def search(self, query: RetrievalQuery, query_vector: List[float]) -> List[RetrievalResult]:
        qdrant_filter = None
        if query.category_filter:
            qdrant_filter = Filter(
                must=[
                    FieldCondition(
                        key="category",
                        match=MatchValue(value=query.category_filter),
                    )
                ]
            )

        results = self._client.search(
            collection_name=self.collection,
            query_vector=query_vector,
            limit=query.top_k,
            score_threshold=query.min_score,
            query_filter=qdrant_filter,
            with_payload=True,
        )

        retrieval_results = []
        for hit in results:
            record = KBRecord(**hit.payload)
            citation = _build_citation(record)
            retrieval_results.append(
                RetrievalResult(record=record, score=hit.score, citation=citation)
            )
        return retrieval_results

    def delete_collection(self) -> None:
        self._client.delete_collection(self.collection)


# ---------------------------------------------------------------------------
# Pinecone Vector Store (production)
# ---------------------------------------------------------------------------

class PineconeVectorStore:
    """
    Pinecone serverless store for production use.
    Requires PINECONE_API_KEY, PINECONE_ENVIRONMENT, PINECONE_INDEX_NAME.
    """

    def __init__(self):
        try:
            from pinecone import Pinecone, ServerlessSpec
            self._pc = Pinecone(api_key=settings.pinecone_api_key)
            index_name = settings.pinecone_index_name

            if index_name not in [i.name for i in self._pc.list_indexes().indexes]:
                self._pc.create_index(
                    name=index_name,
                    dimension=VECTOR_DIM,
                    metric="cosine",
                    spec=ServerlessSpec(cloud="aws", region="us-east-1"),
                )
            self._index = self._pc.Index(index_name)
            logger.info("pinecone_connected", index=index_name)
        except Exception as e:
            logger.error("pinecone_init_failed", error=str(e))
            raise

    def upsert(self, records: List[KBRecord], vectors: List[List[float]]) -> None:
        batch = []
        for record, vector in zip(records, vectors):
            metadata = {
                "title": record.title,
                "category": record.category,
                "source_id": record.source_id,
                "source_url": record.source_url,
                "language": record.language,
                "content": record.content[:1000],  # Pinecone metadata limit
            }
            batch.append((record.record_id, vector, metadata))

        # Pinecone recommends batches of 100
        for i in range(0, len(batch), 100):
            self._index.upsert(vectors=batch[i : i + 100])
        logger.info("pinecone_upserted", count=len(batch))

    def search(self, query: RetrievalQuery, query_vector: List[float]) -> List[RetrievalResult]:
        filter_dict: Dict[str, Any] = {}
        if query.category_filter:
            filter_dict["category"] = {"$eq": query.category_filter}

        response = self._index.query(
            vector=query_vector,
            top_k=query.top_k,
            include_metadata=True,
            filter=filter_dict or None,
        )

        results = []
        for match in response.matches:
            if match.score < query.min_score:
                continue
            meta = match.metadata
            record = KBRecord(
                record_id=match.id,
                title=meta.get("title", ""),
                content=meta.get("content", ""),
                category=meta.get("category", "faq"),
                source_id=meta.get("source_id", ""),
                source_type="website",
                source_url=meta.get("source_url", ""),
                language=meta.get("language", "en-PH"),
            )
            citation = _build_citation(record)
            results.append(RetrievalResult(record=record, score=match.score, citation=citation))
        return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_citation(record: KBRecord) -> str:
    """
    Produces a short human-readable citation string.
    Format: [Title] — source_type: source_url (version)
    """
    return f"[{record.title}] — {record.source_type}: {record.source_url} (v{record.version})"


def get_vector_store():
    """
    Factory — returns the right vector store based on environment.

    Priority:
      1. Pinecone  — if APP_ENV=production and PINECONE_API_KEY set
      2. Qdrant on-disk — default for local dev (no Docker needed)
         Data saved to ./q2_knowledge_base/embeddings/ folder
    """
    if settings.app_env == "production" and settings.pinecone_api_key:
        return PineconeVectorStore()
    return QdrantVectorStore()
