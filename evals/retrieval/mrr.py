"""Mean Reciprocal Rank (MRR) evaluation metric for RAG retrieval quality."""

from __future__ import annotations


def reciprocal_rank(retrieved_ids: list[str], relevant_ids: list[str]) -> float:
    """
    Compute Reciprocal Rank for a single query.

    Returns 1/rank for the first relevant document found,
    or 0.0 if no relevant document appears in the results.

    Args:
        retrieved_ids: Ordered list of retrieved document IDs (best first)
        relevant_ids: Set of ground-truth relevant document IDs

    Returns:
        Reciprocal rank in [0.0, 1.0]
    """
    relevant = set(relevant_ids)
    for rank, doc_id in enumerate(retrieved_ids, start=1):
        if doc_id in relevant:
            return 1.0 / rank
    return 0.0


def mean_reciprocal_rank(queries: list[dict]) -> float:
    """
    Compute Mean Reciprocal Rank across a batch of queries.

    Each query dict must have keys:
      - "retrieved": list[str] of retrieved doc IDs (ranked)
      - "relevant": list[str] of ground-truth relevant doc IDs

    Args:
        queries: List of query dicts

    Returns:
        MRR score in [0.0, 1.0]
    """
    if not queries:
        return 0.0
    rr_scores = [
        reciprocal_rank(q.get("retrieved", []), q.get("relevant", []))
        for q in queries
    ]
    return sum(rr_scores) / len(rr_scores)
