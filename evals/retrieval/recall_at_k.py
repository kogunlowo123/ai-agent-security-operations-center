"""Recall@K evaluation metric for RAG retrieval quality."""

from __future__ import annotations


def recall_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> float:
    """
    Compute Recall@K for a single query.

    Args:
        retrieved_ids: Ordered list of retrieved document IDs (best first)
        relevant_ids: Set of ground-truth relevant document IDs
        k: Cutoff rank

    Returns:
        Recall@K in [0.0, 1.0]
    """
    if not relevant_ids:
        return 0.0
    top_k = set(retrieved_ids[:k])
    relevant = set(relevant_ids)
    return len(top_k & relevant) / len(relevant)


def batch_recall_at_k(queries: list[dict], k: int = 10) -> float:
    """
    Compute mean Recall@K across a batch of queries.

    Each query dict must have keys:
      - "retrieved": list[str] of retrieved doc IDs
      - "relevant": list[str] of ground-truth relevant doc IDs

    Args:
        queries: List of query dicts with "retrieved" and "relevant" keys
        k: Cutoff rank

    Returns:
        Average Recall@K across all queries
    """
    if not queries:
        return 0.0
    scores = [
        recall_at_k(q.get("retrieved", []), q.get("relevant", []), k)
        for q in queries
    ]
    return sum(scores) / len(scores)
