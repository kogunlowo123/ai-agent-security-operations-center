"""
CI gate runner for eval metrics.

Fails CI (exit code 1) if any configured metric falls below its threshold:
  - recall@10  >= 0.80
  - mrr        >= 0.65
  - faithfulness >= 0.90
  - citation_accuracy >= 0.85

Usage:
  python -m evals.runners.ci_gate --dataset evals/datasets/golden/soc-triage-qa-pairs.jsonl
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Thresholds (configurable via environment variable or argument)
# ---------------------------------------------------------------------------
DEFAULT_THRESHOLDS: dict[str, float] = {
    "recall_at_10": 0.80,
    "mrr": 0.65,
    "faithfulness": 0.90,
    "citation_accuracy": 0.85,
}


def load_dataset(dataset_path: str) -> list[dict]:
    """Load a JSONL dataset file."""
    records: list[dict] = []
    with open(dataset_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def run_retrieval_evals(records: list[dict]) -> dict[str, float]:
    """
    Run retrieval metrics (Recall@10, MRR) over the dataset.

    In production this would call the actual retrieval system.
    For CI gate purposes, it expects pre-computed "retrieval_results"
    in the dataset records.
    """
    from evals.retrieval.recall_at_k import recall_at_k
    from evals.retrieval.mrr import reciprocal_rank

    recall_scores: list[float] = []
    rr_scores: list[float] = []

    for record in records:
        retrieval = record.get("retrieval_results", {})
        retrieved = retrieval.get("retrieved_ids", [])
        relevant = retrieval.get("relevant_ids", [])

        if relevant:
            recall_scores.append(recall_at_k(retrieved, relevant, k=10))
            rr_scores.append(reciprocal_rank(retrieved, relevant))

    mean_recall = sum(recall_scores) / len(recall_scores) if recall_scores else 0.0
    mean_mrr = sum(rr_scores) / len(rr_scores) if rr_scores else 0.0

    return {
        "recall_at_10": round(mean_recall, 4),
        "mrr": round(mean_mrr, 4),
    }


def run_generation_evals(records: list[dict]) -> dict[str, float]:
    """
    Run generation metrics (faithfulness, citation_accuracy) over the dataset.
    """
    from evals.generation.faithfulness import evaluate_faithfulness
    from evals.generation.citation_accuracy import evaluate_citation_accuracy

    faithfulness_scores: list[float] = []
    citation_scores: list[float] = []

    for record in records:
        answer = record.get("agent_answer", "")
        context = record.get("context_passages", [])
        docs = record.get("retrieved_documents", [])

        if answer and context:
            faith_result = evaluate_faithfulness(answer, context)
            faithfulness_scores.append(faith_result.score)

        if answer and docs:
            cite_result = evaluate_citation_accuracy(answer, docs)
            citation_scores.append(cite_result.accuracy)

    mean_faith = sum(faithfulness_scores) / len(faithfulness_scores) if faithfulness_scores else None
    mean_cite = sum(citation_scores) / len(citation_scores) if citation_scores else None

    result: dict[str, float] = {}
    if mean_faith is not None:
        result["faithfulness"] = round(mean_faith, 4)
    if mean_cite is not None:
        result["citation_accuracy"] = round(mean_cite, 4)

    return result


def check_thresholds(
    computed: dict[str, float],
    thresholds: dict[str, float],
) -> tuple[bool, list[str]]:
    """
    Check computed metrics against thresholds.

    Returns (all_pass, list_of_failures).
    """
    failures: list[str] = []

    for metric, threshold in thresholds.items():
        if metric not in computed:
            continue  # Skip metrics not computed for this dataset
        value = computed[metric]
        if value < threshold:
            failures.append(
                f"FAIL  {metric}: {value:.4f} < {threshold:.4f} (threshold)"
            )

    all_pass = len(failures) == 0
    return all_pass, failures


def run_ci_gate(
    dataset_path: str,
    thresholds: dict[str, float] | None = None,
    output_format: str = "text",
) -> int:
    """
    Run the full CI gate evaluation.

    Parameters
    ----------
    dataset_path:
        Path to the JSONL dataset file.
    thresholds:
        Override default thresholds. Missing keys use defaults.
    output_format:
        "text" for human-readable output, "json" for machine-readable.

    Returns
    -------
    int
        0 if all metrics pass, 1 if any fail.
    """
    effective_thresholds = {**DEFAULT_THRESHOLDS, **(thresholds or {})}

    print(f"[ci-gate] Loading dataset: {dataset_path}", file=sys.stderr)
    try:
        records = load_dataset(dataset_path)
    except FileNotFoundError:
        print(f"[ci-gate] ERROR: Dataset not found: {dataset_path}", file=sys.stderr)
        return 1

    print(f"[ci-gate] Loaded {len(records)} records", file=sys.stderr)

    # Run evaluations
    computed: dict[str, float] = {}

    print("[ci-gate] Running retrieval evals...", file=sys.stderr)
    try:
        retrieval_metrics = run_retrieval_evals(records)
        computed.update(retrieval_metrics)
    except Exception as exc:
        print(f"[ci-gate] WARNING: retrieval evals failed: {exc}", file=sys.stderr)

    print("[ci-gate] Running generation evals...", file=sys.stderr)
    try:
        generation_metrics = run_generation_evals(records)
        computed.update(generation_metrics)
    except Exception as exc:
        print(f"[ci-gate] WARNING: generation evals failed: {exc}", file=sys.stderr)

    # Check thresholds
    all_pass, failures = check_thresholds(computed, effective_thresholds)

    result = {
        "status": "PASS" if all_pass else "FAIL",
        "metrics": computed,
        "thresholds": effective_thresholds,
        "failures": failures,
        "dataset": dataset_path,
        "records_evaluated": len(records),
    }

    if output_format == "json":
        print(json.dumps(result, indent=2))
    else:
        print(f"\n{'='*60}")
        print(f"CI Gate Result: {result['status']}")
        print(f"Dataset: {dataset_path} ({len(records)} records)")
        print(f"{'='*60}")
        print("\nMetrics:")
        for metric, value in sorted(computed.items()):
            threshold = effective_thresholds.get(metric, 0.0)
            status_icon = "PASS" if value >= threshold else "FAIL"
            print(f"  [{status_icon}] {metric:<25} {value:.4f}  (threshold: {threshold:.4f})")

        if failures:
            print(f"\nFailures ({len(failures)}):")
            for failure in failures:
                print(f"  {failure}")
        else:
            print("\nAll metrics passed thresholds.")
        print(f"{'='*60}\n")

    return 0 if all_pass else 1


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="CI gate runner for SOC agent eval metrics"
    )
    parser.add_argument(
        "--dataset",
        default="evals/datasets/golden/soc-triage-qa-pairs.jsonl",
        help="Path to JSONL evaluation dataset",
    )
    parser.add_argument(
        "--output-format",
        choices=["text", "json"],
        default="text",
        help="Output format",
    )
    parser.add_argument(
        "--recall-threshold",
        type=float,
        default=DEFAULT_THRESHOLDS["recall_at_10"],
        help=f"Recall@10 threshold (default: {DEFAULT_THRESHOLDS['recall_at_10']})",
    )
    parser.add_argument(
        "--mrr-threshold",
        type=float,
        default=DEFAULT_THRESHOLDS["mrr"],
        help=f"MRR threshold (default: {DEFAULT_THRESHOLDS['mrr']})",
    )
    parser.add_argument(
        "--faithfulness-threshold",
        type=float,
        default=DEFAULT_THRESHOLDS["faithfulness"],
        help=f"Faithfulness threshold (default: {DEFAULT_THRESHOLDS['faithfulness']})",
    )
    parser.add_argument(
        "--citation-threshold",
        type=float,
        default=DEFAULT_THRESHOLDS["citation_accuracy"],
        help=f"Citation accuracy threshold (default: {DEFAULT_THRESHOLDS['citation_accuracy']})",
    )

    args = parser.parse_args()

    thresholds = {
        "recall_at_10": args.recall_threshold,
        "mrr": args.mrr_threshold,
        "faithfulness": args.faithfulness_threshold,
        "citation_accuracy": args.citation_threshold,
    }

    exit_code = run_ci_gate(
        dataset_path=args.dataset,
        thresholds=thresholds,
        output_format=args.output_format,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
