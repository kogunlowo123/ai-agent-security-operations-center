"""Normalized Discounted Cumulative Gain (nDCG@K) evaluation metric."""

from __future__ import annotations

import math


def dcg_at_k(relevance_scores: list[float], k: int) -> float:
    """
    Compute Discounted Cumulative Gain at rank K.

    Args:
        relevance_scores: Graded relevance scores ordered by retrieved rank
        k: Cutoff rank

    Returns:
        DCG@K score
    """
    dcg = 0.0
    for i, rel in enumerate(relevance_scores[:k], start=1):
        dcg += rel / math.log2(i + 1)
    return dcg


def idcg_at_k(relevance_scores: list[float], k: int) -> float:
    """
    Compute Ideal Discounted Cumulative Gain at rank K.

    Sorts scores in descending order to compute the ideal ranking.
    """
    ideal = sorted(relevance_scores, reverse=True)
    return dcg_at_k(ideal, k)


def ndcg_at_k(retrieved_ids: list[str], relevance_map: dict[str, float], k: int) -> float:
    """
    Compute nDCG@K for a single query.

    Args:
        retrieved_ids: Ordered list of retrieved document IDs (best first)
        relevance_map: Dict mapping document ID → relevance grade (0.0–3.0 typical)
        k: Cutoff rank

    Returns:
        nDCG@K in [0.0, 1.0]
    """
    if not relevance_map:
        return 0.0

    retrieved_scores = [relevance_map.get(doc_id, 0.0) for doc_id in retrieved_ids[:k]]
    all_scores = list(relevance_map.values())

    actual_dcg = dcg_at_k(retrieved_scores, k)
    ideal_dcg = idcg_at_k(all_scores, k)

    if ideal_dcg == 0.0:
        return 0.0
    return actual_dcg / ideal_dcg


def binary_relevance_ndcg(
    retrieved_ids: list[str],
    relevant_ids: list[str],
    k: int = 10,
) -> float:
    """
    Compute nDCG@K using binary relevance (relevant=1.0, not-relevant=0.0).

    Convenience wrapper for evaluation datasets where relevance is binary.
    """
    relevance_map = {doc_id: 1.0 for doc_id in relevant_ids}
    return ndcg_at_k(retrieved_ids, relevance_map, k)


def batch_ndcg_at_k(queries: list[dict], k: int = 10) -> float:
    """
    Compute mean nDCG@K across a batch of queries.

    Each query dict must have:
      - "retrieved": list[str] of retrieved doc IDs
      - "relevant": list[str] of ground-truth relevant doc IDs (binary relevance)
    """
    if not queries:
        return 0.0
    scores = [
        binary_relevance_ndcg(
            q.get("retrieved", []),
            q.get("relevant", []),
            k,
        )
        for q in queries
    ]
    return sum(scores) / len(scores)
