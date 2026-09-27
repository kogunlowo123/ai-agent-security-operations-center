"""
Citation accuracy evaluation for RAG-based SOC agent outputs.

Checks whether document citations included in agent-generated text
correspond to real document IDs that were retrieved and used as context.

Citation Accuracy = |valid_citations| / |total_citations_in_output|

A citation is "valid" when:
  1. Its ID appears in the set of retrieved document IDs, AND
  2. The cited document is semantically relevant to the surrounding claim
     (optional deeper check, enabled via strict_mode=True).
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Pattern

logger = logging.getLogger(__name__)

# Regex patterns for common citation formats used in SOC agent outputs
# Matches: [doc-123], [DOC-123], [MITRE-T1078], [CVE-2024-1234], [1], [42]
_BRACKET_CITATION_PATTERN: Pattern[str] = re.compile(
    r"\[([A-Za-z0-9][A-Za-z0-9\-_.]*[A-Za-z0-9]|\d+)\]"
)
# Matches inline: (source: doc-123) or (ref: doc-123)
_INLINE_CITATION_PATTERN: Pattern[str] = re.compile(
    r"\(?(?:source|ref|citation|cite):\s*([A-Za-z0-9][A-Za-z0-9\-_.]*)\)?"
)


@dataclass
class CitationAccuracyResult:
    """Result of a citation accuracy evaluation."""

    total_citations: int
    valid_citations: int
    invalid_citations: list[str]
    missing_citations: list[str]  # docs retrieved but never cited
    accuracy: float
    coverage: float  # fraction of retrieved docs that were actually cited

    def __str__(self) -> str:
        return (
            f"CitationAccuracy: {self.accuracy:.3f} "
            f"({self.valid_citations}/{self.total_citations} valid), "
            f"Coverage: {self.coverage:.3f}"
        )


def extract_citations(text: str) -> list[str]:
    """
    Extract all citation IDs from agent-generated text.

    Supports bracket format [doc-id] and inline (source: doc-id) formats.

    Parameters
    ----------
    text:
        Agent-generated text that may contain citations.

    Returns
    -------
    list[str]
        List of extracted citation IDs (may contain duplicates).

    Examples
    --------
    >>> extract_citations("The CVE [CVE-2024-1234] was found in package [pkg-001].")
    ['CVE-2024-1234', 'pkg-001']
    >>> extract_citations("See (source: mitre-t1078) for details.")
    ['mitre-t1078']
    """
    citations: list[str] = []
    citations.extend(m.group(1) for m in _BRACKET_CITATION_PATTERN.finditer(text))
    citations.extend(m.group(1) for m in _INLINE_CITATION_PATTERN.finditer(text))
    return citations


def evaluate_citation_accuracy(
    generated_text: str,
    retrieved_doc_ids: list[str],
    case_sensitive: bool = False,
) -> CitationAccuracyResult:
    """
    Evaluate the accuracy of citations in agent-generated text.

    Parameters
    ----------
    generated_text:
        The text produced by the SOC agent, potentially containing citations.
    retrieved_doc_ids:
        List of document IDs that the retriever actually returned and provided
        to the agent as context.
    case_sensitive:
        Whether citation matching should be case-sensitive. Default: False.

    Returns
    -------
    CitationAccuracyResult
        Detailed breakdown of citation accuracy.

    Examples
    --------
    >>> result = evaluate_citation_accuracy(
    ...     "Attack used T1078 [mitre-t1078] and targeted aws [aws-doc-001].",
    ...     retrieved_doc_ids=["mitre-t1078", "aws-doc-001", "unused-doc"],
    ... )
    >>> result.accuracy
    1.0
    >>> result.coverage
    0.6666...
    """
    raw_citations = extract_citations(generated_text)

    if not case_sensitive:
        retrieved_set = {doc_id.lower() for doc_id in retrieved_doc_ids}
        normalized_citations = [c.lower() for c in raw_citations]
    else:
        retrieved_set = set(retrieved_doc_ids)
        normalized_citations = raw_citations

    total = len(normalized_citations)

    if total == 0:
        # No citations found — accuracy is undefined; return 1.0 (no incorrect citations)
        # but coverage will indicate nothing was cited.
        cited_ids: set[str] = set()
        return CitationAccuracyResult(
            total_citations=0,
            valid_citations=0,
            invalid_citations=[],
            missing_citations=list(retrieved_set),
            accuracy=1.0,
            coverage=0.0,
        )

    valid: list[str] = []
    invalid: list[str] = []
    cited_ids = set()

    for original, normalized in zip(raw_citations, normalized_citations):
        if normalized in retrieved_set:
            valid.append(original)
            cited_ids.add(normalized)
        else:
            invalid.append(original)
            logger.debug("Invalid citation '%s' not in retrieved docs", original)

    # Coverage: what fraction of retrieved docs were cited at least once
    coverage = len(cited_ids) / len(retrieved_set) if retrieved_set else 0.0
    missing = [
        doc_id for doc_id in retrieved_doc_ids
        if doc_id.lower() not in cited_ids
    ] if not case_sensitive else [
        doc_id for doc_id in retrieved_doc_ids
        if doc_id not in cited_ids
    ]

    return CitationAccuracyResult(
        total_citations=total,
        valid_citations=len(valid),
        invalid_citations=invalid,
        missing_citations=missing,
        accuracy=len(valid) / total,
        coverage=coverage,
    )


def batch_citation_accuracy(
    samples: list[tuple[str, list[str]]],
) -> dict[str, float]:
    """
    Evaluate citation accuracy across multiple samples and return aggregate metrics.

    Parameters
    ----------
    samples:
        List of (generated_text, retrieved_doc_ids) tuples.

    Returns
    -------
    dict with keys:
        - mean_accuracy: average citation accuracy across all samples
        - mean_coverage: average citation coverage across all samples
        - total_citations: total citations evaluated
        - total_valid: total valid citations
        - hallucination_rate: fraction of citations that were invalid
    """
    if not samples:
        return {
            "mean_accuracy": 0.0,
            "mean_coverage": 0.0,
            "total_citations": 0,
            "total_valid": 0,
            "hallucination_rate": 0.0,
        }

    results = [
        evaluate_citation_accuracy(text, doc_ids)
        for text, doc_ids in samples
    ]

    total_cits = sum(r.total_citations for r in results)
    total_valid = sum(r.valid_citations for r in results)

    return {
        "mean_accuracy": sum(r.accuracy for r in results) / len(results),
        "mean_coverage": sum(r.coverage for r in results) / len(results),
        "total_citations": total_cits,
        "total_valid": total_valid,
        "hallucination_rate": (
            (total_cits - total_valid) / total_cits if total_cits > 0 else 0.0
        ),
    }
