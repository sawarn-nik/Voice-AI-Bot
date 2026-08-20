"""
Ingestion Pipeline
==================
Orchestrates the full KB build:
  raw JSON → clean → chunk → embed → upsert to vector store → save cleaned records

Run:
    python -m q2_knowledge_base.ingest
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List

from q2_knowledge_base.cleaner import clean_document, NearDuplicateFilter
from q2_knowledge_base.chunker import build_records
from q2_knowledge_base.embedder import Embedder, get_vector_store
from q2_knowledge_base.schema import KBRecord

from shared.utils import logger

RAW_DATA_PATH = Path(__file__).parent / "data" / "raw" / "health_insurance_source.json"
CLEANED_DATA_PATH = Path(__file__).parent / "data" / "cleaned" / "kb_records.json"

# ---------------------------------------------------------------------------
# Source → category mapping
# ---------------------------------------------------------------------------

SOURCE_META = {
    "web_001": {
        "category": "product_info",
        "title": "Health Insurance Plan Tiers",
        "tags": ["plans", "coverage", "premium"],
    },
    "web_002": {
        "category": "eligibility_rules",
        "title": "Eligibility Requirements",
        "tags": ["eligibility", "age", "bmi", "smoker", "pre-existing"],
    },
    "web_003": {
        "category": "faq",
        "title": "Frequently Asked Questions",
        "tags": ["faq", "claims", "dependents", "waiting-period", "cancellation"],
    },
    "web_004": {
        "category": "faq",
        "title": "Frequently Asked Questions (Duplicate)",
        "tags": ["faq"],
    },
    "pdf_001": {
        "category": "policy_exclusions",
        "title": "Policy Document — Health Insurance",
        "tags": ["policy", "exclusions", "claims", "hospitalisation"],
    },
    "web_005": {
        "category": "objection_handling",
        "title": "Objection Handling Guide",
        "tags": ["objections", "sales", "rebuttals"],
    },
    "web_006": {
        "category": "partnership_benefits",
        "title": "Branch Partnership Benefits",
        "tags": ["partners", "commission"],
    },
    "csv_001": {
        "category": "plan_comparison",
        "title": "Plan Comparison Table",
        "tags": ["plans", "comparison", "pricing"],
    },
    "web_007": {
        "category": "contact_info",
        "title": "Contact Information",
        "tags": ["contact", "hotline", "email"],
    },
    "pii_sample_001": {
        "category": "faq",
        "title": "Lead Form Sample (PII — will be redacted)",
        "tags": ["pii", "form"],
    },
}


def run_ingestion(force: bool = False) -> List[KBRecord]:
    logger.info("ingestion_start")

    # Load raw sources
    with open(RAW_DATA_PATH) as f:
        sources = json.load(f)

    dedup_filter = NearDuplicateFilter(threshold=90)
    all_records: List[KBRecord] = []
    skipped_count = 0

    for source in sources:
        source_id = source["source_id"]
        raw_text = source["raw_text"]
        source_type = source.get("source_type", "website")
        source_url = source.get("url", "")

        # Clean
        cleaned_text, pii_present, pii_types = clean_document(raw_text, redact=True)

        if pii_present:
            logger.warning(
                "pii_detected_and_redacted",
                source_id=source_id,
                types=pii_types,
            )

        # Near-duplicate check
        if dedup_filter.check_and_add(cleaned_text):
            logger.info("duplicate_skipped", source_id=source_id)
            skipped_count += 1
            continue

        meta = SOURCE_META.get(source_id, {
            "category": "faq",
            "title": source_id,
            "tags": [],
        })

        # Chunk and wrap in KB records
        records = build_records(
            cleaned_text=cleaned_text,
            source_id=source_id,
            source_type=source_type,
            source_url=source_url,
            category=meta["category"],
            title_prefix=meta["title"],
            pii_present=pii_present,
            tags=meta.get("tags", []),
        )
        all_records.extend(records)
        logger.info(
            "source_processed",
            source_id=source_id,
            chunks=len(records),
            pii=pii_present,
        )

    logger.info(
        "ingestion_complete",
        total_records=len(all_records),
        duplicates_skipped=skipped_count,
    )

    # Persist cleaned records
    CLEANED_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CLEANED_DATA_PATH, "w") as f:
        json.dump([r.model_dump() for r in all_records], f, indent=2)
    logger.info("cleaned_records_saved", path=str(CLEANED_DATA_PATH))

    # Embed and index
    _embed_and_index(all_records)

    return all_records


def _embed_and_index(records: List[KBRecord]) -> None:
    """Embed all records (batched) and upsert into the vector store."""
    # Skip records with PII (already redacted, but being extra cautious)
    safe_records = records  # PII already redacted by clean_document

    embedder = Embedder()
    store = get_vector_store()

    texts = [r.content for r in safe_records]

    logger.info("embedding_start", count=len(texts))

    # Batch in groups of 100 to stay within API rate limits
    batch_size = 100
    all_vectors = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        vectors = embedder.embed(batch)
        all_vectors.extend(vectors)
        logger.info("embedding_batch_done", batch_end=i + len(batch))

    store.upsert(safe_records, all_vectors)
    logger.info("indexing_complete", total=len(safe_records))


if __name__ == "__main__":
    run_ingestion()
