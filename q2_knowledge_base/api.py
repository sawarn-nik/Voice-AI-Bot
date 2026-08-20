"""
Knowledge Base REST API
=======================
Exposes retrieval over HTTP so the voice agent (and any other service)
can query the KB without direct Python imports.

Endpoints
---------
POST /retrieve          — semantic search
GET  /records/{id}      — fetch record by ID
GET  /health            — liveness check

Run:
    uvicorn q2_knowledge_base.api:app --port 8001 --reload
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import json
from pathlib import Path

from q2_knowledge_base.retriever import Retriever
from q2_knowledge_base.schema import RetrievalResult, CategoryType

app = FastAPI(
    title="Darwix Knowledge Base API",
    version="1.0.0",
    description="Semantic retrieval API for the health insurance knowledge base.",
)

_retriever: Optional[Retriever] = None


def get_retriever() -> Retriever:
    global _retriever
    if _retriever is None:
        _retriever = Retriever()
    return _retriever


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class RetrieveRequest(BaseModel):
    query: str
    top_k: int = 5
    category_filter: Optional[CategoryType] = None
    min_score: float = 0.45


class RetrieveResponseItem(BaseModel):
    record_id: str
    title: str
    content: str
    category: str
    source_url: str
    score: float
    citation: str
    language: str


class RetrieveResponse(BaseModel):
    query: str
    results: List[RetrieveResponseItem]
    context_text: str
    found: bool


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok", "service": "knowledge_base"}


@app.post("/retrieve", response_model=RetrieveResponse)
async def retrieve(req: RetrieveRequest):
    retriever = get_retriever()
    context_text, results = retriever.search_grounded(
        query=req.query,
        top_k=req.top_k,
        category_filter=req.category_filter,
        min_score=req.min_score,
    )

    items = [
        RetrieveResponseItem(
            record_id=r.record.record_id,
            title=r.record.title,
            content=r.record.content,
            category=r.record.category,
            source_url=r.record.source_url,
            score=r.score,
            citation=r.citation,
            language=r.record.language,
        )
        for r in results
    ]

    return RetrieveResponse(
        query=req.query,
        results=items,
        context_text=context_text,
        found=len(items) > 0,
    )


@app.get("/records/{record_id}")
async def get_record(record_id: str):
    """Fetch a specific record by ID from the saved cleaned records file."""
    cleaned_path = Path(__file__).parent / "data" / "cleaned" / "kb_records.json"
    if not cleaned_path.exists():
        raise HTTPException(status_code=503, detail="Knowledge base not yet built. Run ingestion first.")

    with open(cleaned_path) as f:
        records = json.load(f)

    for r in records:
        if r["record_id"] == record_id:
            return r

    raise HTTPException(status_code=404, detail=f"Record {record_id} not found.")
