"""
Data Cleaning Pipeline
======================
Transforms raw source documents into clean text suitable for chunking.

Steps
-----
1. Strip navigation boilerplate (headers, footers, nav links, cookie notices)
2. Normalise whitespace, dashes, and unicode
3. Detect and redact PII
4. Deduplicate near-identical content using fuzzy hashing
5. Standardise terminology and abbreviations
"""

from __future__ import annotations

import re
import hashlib
import unicodedata
from typing import List, Tuple

from rapidfuzz import fuzz

# ---------------------------------------------------------------------------
# Boilerplate patterns to strip
# ---------------------------------------------------------------------------

_NAV_PATTERNS = [
    r"\bhome\b\s*[|\/]\s*\babout\b.*",        # "Home | About Us | Contact"
    r"footer.*",
    r"navigation:.*",
    r"site\s*map.*",
    r"privacy\s*policy.*",
    r"cookie\s*policy.*",
    r"©\s*\d{4}.*",
    r"terms\s*(?:of\s*use)?.*",
    r"accessibility.*",
    r"^\s*(?:login|sign\s*in|register)\s*$",
]

_NAV_RE = re.compile("|".join(_NAV_PATTERNS), re.MULTILINE | re.IGNORECASE)

# ---------------------------------------------------------------------------
# PII patterns
# ---------------------------------------------------------------------------

_PII_PATTERNS = {
    "phone_ph": re.compile(r"09\d{9}"),
    "phone_intl": re.compile(r"\+?\d[\d\s\-]{8,14}\d"),
    "email": re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"),
    "full_name_label": re.compile(r"(?i)(name\s*:\s*)([A-Z][a-z]+ [A-Z][a-z]+)"),
    "dob_label": re.compile(r"(?i)(dob\s*:\s*)\d{4}-\d{2}-\d{2}"),
    "nid": re.compile(r"\b\d{3}-\d{7}-\d\b"),  # PH SSS/TIN format
}

# ---------------------------------------------------------------------------
# Terminology standardisation map
# ---------------------------------------------------------------------------

_TERM_MAP = {
    r"\bPhp\b": "PHP",
    r"\bphp\b": "PHP",
    r"\bpeso\b": "PHP",
    r"\bPeso\b": "PHP",
    r"\bdependants\b": "dependents",
    r"\bDependants\b": "Dependents",
    r"\bco-pay\b": "co-payment",
    r"\bcopay\b": "co-payment",
    r"\bpre existing\b": "pre-existing",
    r"\bpreexisting\b": "pre-existing",
    r"\bfree look\b": "free-look",
    r"\bFreeLook\b": "free-look",
    r"\bICU\b": "Intensive Care Unit (ICU)",
    r"\bGP\b": "General Practitioner (GP)",
    r"\bFDA\b": "Food and Drug Administration (FDA)",
}


def _strip_navigation(text: str) -> str:
    """Remove nav/footer boilerplate line by line."""
    lines = text.splitlines()
    cleaned = []
    for line in lines:
        if _NAV_RE.match(line.strip()):
            continue
        cleaned.append(line)
    return "\n".join(cleaned)


def _normalise_whitespace(text: str) -> str:
    """Collapse multiple blank lines, trim edges."""
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"\r\n|\r", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _standardise_terms(text: str) -> str:
    for pattern, replacement in _TERM_MAP.items():
        text = re.sub(pattern, replacement, text)
    return text


def detect_pii(text: str) -> Tuple[bool, List[str]]:
    """
    Returns (has_pii, list_of_pii_types_found).
    Does NOT redact — caller decides what to do.
    """
    found = []
    for label, pattern in _PII_PATTERNS.items():
        if pattern.search(text):
            found.append(label)
    return (len(found) > 0, found)


def redact_pii(text: str) -> str:
    """Replace PII values with placeholder tokens."""
    text = _PII_PATTERNS["email"].sub("[EMAIL_REDACTED]", text)
    text = _PII_PATTERNS["phone_ph"].sub("[PHONE_REDACTED]", text)
    text = _PII_PATTERNS["phone_intl"].sub("[PHONE_REDACTED]", text)
    text = _PII_PATTERNS["full_name_label"].sub(r"\1[NAME_REDACTED]", text)
    text = _PII_PATTERNS["dob_label"].sub(r"\1[DOB_REDACTED]", text)
    text = _PII_PATTERNS["nid"].sub("[ID_REDACTED]", text)
    return text


def content_hash(text: str) -> str:
    """MD5 fingerprint for exact dedup."""
    return hashlib.md5(text.strip().lower().encode()).hexdigest()


class NearDuplicateFilter:
    """
    Maintains a set of seen content fingerprints.
    Uses fuzzy ratio to catch near-duplicates (e.g. same FAQ page crawled twice).
    """

    def __init__(self, threshold: int = 90):
        self._seen: List[str] = []
        self.threshold = threshold

    def is_duplicate(self, text: str) -> bool:
        for seen in self._seen:
            if fuzz.ratio(text, seen) >= self.threshold:
                return True
        return False

    def add(self, text: str) -> None:
        self._seen.append(text)

    def check_and_add(self, text: str) -> bool:
        """Returns True if duplicate (should be skipped), False if new."""
        if self.is_duplicate(text):
            return True
        self.add(text)
        return False


def clean_document(raw_text: str, redact: bool = False) -> Tuple[str, bool, List[str]]:
    """
    Full cleaning pipeline for a single document.

    Returns
    -------
    (cleaned_text, pii_present, pii_types)
    """
    text = _strip_navigation(raw_text)
    text = _normalise_whitespace(text)
    text = _standardise_terms(text)

    pii_present, pii_types = detect_pii(text)

    if redact and pii_present:
        text = redact_pii(text)

    return text, pii_present, pii_types
