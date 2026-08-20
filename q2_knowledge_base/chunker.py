"""
Chunking Strategy
=================
Converts cleaned document text into embedding-ready chunks.

Strategy
--------
- Primary: Semantic / paragraph-aware splitting.
  Split on double newlines first to respect natural paragraph boundaries.
  If a paragraph still exceeds max_tokens, fall back to sliding-window token split.

- Chunk size: 400 tokens (≈ 300 words). Chosen because:
  * Large enough to hold a complete Q&A pair or policy clause.
  * Small enough for precise retrieval — avoids burying the answer.

- Overlap: 80 tokens. Preserves context across chunk boundaries so that
  sentences split at the edge are still retrievable from both sides.

- Metadata injection: each chunk inherits full source metadata and a
  positional index so callers can reconstruct the original document order
  for citation purposes.
"""

from __future__ import annotations

import re
from typing import List

import tiktoken

from q2_knowledge_base.schema import KBRecord, CategoryType, SourceType

# Use cl100k_base (GPT-4 / text-embedding-3 tokeniser)
_ENC = tiktoken.get_encoding("cl100k_base")


def _token_len(text: str) -> int:
    return len(_ENC.encode(text))


def _split_by_tokens(
    text: str,
    max_tokens: int,
    overlap_tokens: int,
) -> List[str]:
    """
    Sliding-window token splitter — fallback for very long paragraphs.
    """
    tokens = _ENC.encode(text)
    chunks = []
    start = 0
    while start < len(tokens):
        end = min(start + max_tokens, len(tokens))
        chunk_tokens = tokens[start:end]
        chunks.append(_ENC.decode(chunk_tokens))
        if end == len(tokens):
            break
        start += max_tokens - overlap_tokens
    return chunks


def chunk_text(
    text: str,
    max_tokens: int = 400,
    overlap_tokens: int = 80,
) -> List[str]:
    """
    Paragraph-aware chunking with token-level fallback.

    1. Split on blank lines (paragraph boundaries).
    2. Merge short paragraphs into a running buffer until it would exceed max_tokens.
    3. If a single paragraph exceeds max_tokens, apply sliding-window split.
    """
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]

    chunks: List[str] = []
    buffer = ""

    for para in paragraphs:
        para_tokens = _token_len(para)

        if para_tokens > max_tokens:
            # Flush current buffer first
            if buffer.strip():
                chunks.append(buffer.strip())
                buffer = ""
            # Split the large paragraph with sliding window
            chunks.extend(_split_by_tokens(para, max_tokens, overlap_tokens))
            continue

        candidate = (buffer + "\n\n" + para).strip() if buffer else para

        if _token_len(candidate) <= max_tokens:
            buffer = candidate
        else:
            # Flush buffer and start fresh with current para
            if buffer.strip():
                chunks.append(buffer.strip())
            # Add overlap: take last overlap_tokens from previous buffer
            overlap_text = ""
            if chunks:
                prev_tokens = _ENC.encode(chunks[-1])
                overlap_tokens_actual = min(overlap_tokens, len(prev_tokens))
                overlap_text = _ENC.decode(prev_tokens[-overlap_tokens_actual:])
            buffer = (overlap_text + "\n\n" + para).strip() if overlap_text else para

    if buffer.strip():
        chunks.append(buffer.strip())

    return [c for c in chunks if c.strip()]


def build_records(
    cleaned_text: str,
    source_id: str,
    source_type: SourceType,
    source_url: str,
    category: CategoryType,
    title_prefix: str,
    language: str = "en-PH",
    pii_present: bool = False,
    tags: List[str] = None,
    version: str = "1.0",
    max_tokens: int = 400,
    overlap_tokens: int = 80,
) -> List[KBRecord]:
    """
    Chunk a cleaned document and wrap each chunk in a KBRecord.
    """
    tags = tags or []
    chunks = chunk_text(cleaned_text, max_tokens, overlap_tokens)
    records: List[KBRecord] = []

    for i, chunk in enumerate(chunks):
        # Derive a descriptive title from the first line of the chunk
        first_line = chunk.splitlines()[0][:80].strip()
        title = f"{title_prefix} — Part {i + 1}" if len(chunks) > 1 else title_prefix

        record = KBRecord(
            record_id=f"kb_{source_id}_{i:03d}",
            title=title,
            content=chunk,
            category=category,
            source_id=source_id,
            source_type=source_type,
            source_url=source_url,
            version=version,
            language=language,
            pii_present=pii_present,
            tags=tags,
            chunk_index=i,
            chunk_total=len(chunks),
        )
        records.append(record)

    return records
