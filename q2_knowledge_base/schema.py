"""
Knowledge Base Schema
=====================
Defines the canonical data model for every record in the knowledge base.
All ingested content is normalised to this schema before embedding/indexing.
"""

from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime
import uuid


# ---------------------------------------------------------------------------
# Taxonomy
# ---------------------------------------------------------------------------

CategoryType = Literal[
    "product_info",
    "eligibility_rules",
    "faq",
    "objection_handling",
    "claims_procedure",
    "policy_exclusions",
    "pricing",
    "partnership_benefits",
    "contact_info",
    "plan_comparison",
]

SourceType = Literal["website", "pdf", "table", "form", "internal_guide"]


# ---------------------------------------------------------------------------
# Core KB Record
# ---------------------------------------------------------------------------

class KBRecord(BaseModel):
    """
    A single knowledge-base chunk ready for embedding and retrieval.

    Field          Description
    ──────────     ────────────────────────────────────────────────
    record_id      Unique, stable identifier  (kb_<category>_<seq>)
    title          Human-readable title for the chunk
    content        Clean, normalised text for embedding & display
    category       Taxonomy label (see CategoryType)
    source_id      Original source document identifier
    source_type    Type of source document
    source_url     Origin URL or file path
    version        Schema/content version string
    language       BCP-47 language tag (default: en-PH)
    pii_present    True if the record contains PII (should be redacted before indexing)
    tags           Optional free-form tags for filtering
    created_at     ISO-8601 timestamp of ingestion
    updated_at     ISO-8601 timestamp of last update
    chunk_index    Position of chunk within the parent document
    chunk_total    Total chunks from parent document
    """

    record_id: str = Field(default_factory=lambda: f"kb_{uuid.uuid4().hex[:8]}")
    title: str
    content: str
    category: CategoryType
    source_id: str
    source_type: SourceType
    source_url: str
    version: str = "1.0"
    language: str = "en-PH"
    pii_present: bool = False
    tags: List[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    chunk_index: int = 0
    chunk_total: int = 1

    class Config:
        json_schema_extra = {
            "example": {
                "record_id": "kb_product_001",
                "title": "Branch Partnership Benefits",
                "content": "Operational, marketing, and technology support is provided to branch partners.",
                "category": "partnership_benefits",
                "source_id": "web_006",
                "source_type": "website",
                "source_url": "https://example-insurer.com/branch-partners",
                "version": "1.0",
                "language": "en-PH",
                "pii_present": False,
                "tags": ["partners", "commission"],
                "created_at": "2024-01-01T00:00:00",
                "updated_at": "2024-01-01T00:00:00",
                "chunk_index": 0,
                "chunk_total": 1,
            }
        }


# ---------------------------------------------------------------------------
# Retrieval Result
# ---------------------------------------------------------------------------

class RetrievalResult(BaseModel):
    """Wraps a KB record with its retrieval score and citation."""

    record: KBRecord
    score: float = Field(..., ge=0.0, le=1.0, description="Cosine similarity score")
    citation: str = Field(..., description="Human-readable source citation")

    @property
    def is_confident(self) -> bool:
        return self.score >= 0.60


# ---------------------------------------------------------------------------
# Retrieval Query
# ---------------------------------------------------------------------------

class RetrievalQuery(BaseModel):
    query: str
    top_k: int = 5
    category_filter: Optional[CategoryType] = None
    language_filter: Optional[str] = None
    min_score: float = 0.45
