"""
Click CLI for running SOC agent evals locally.

Usage examples:
  python -m evals.runners.cli --dataset evals/datasets/golden/soc-triage-qa-pairs.jsonl
  python -m evals.runners.cli --dataset ... --metric recall_at_10 --output-format json
  python -m evals.runners.cli --dataset ... --metric all --k 5
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

try:
    import click
except ImportError:
    # Provide a minimal stub so the module can be imported without click
    class _FallbackCLI:
        def command(self, *a, **kw):
            def decorator(fn):
                return fn
            return decorator
        def option(self, *a, **kw):
            def decorator(fn):
                return fn
            return decorator
        def argument(self, *a, **kw):
            def decorator(fn):
                return fn
            return decorator
        def Choice(self, *a, **kw):
            return None
        def group(self, *a, **kw):
            return self.command(*a, **kw)
    click = _FallbackCLI()

    def main():
        print("ERROR: 'click' package is not installed. Run: pip install click", file=sys.stderr)
        sys.exit(1)
else:
    SUPPORTED_METRICS = [
        "recall_at_k",
        "mrr",
        "ndcg",
        "faithfulness",
        "citation_accuracy",
        "refusal_correctness",
        "trajectory",
        "tool_correctness",
        "all",
    ]

    @click.group()
    def cli():
        """SOC agent eval runner CLI."""
        pass

    @cli.command()
    @click.option(
        "--dataset",
        "-d",
        required=True,
        type=click.Path(exists=True, readable=True),
        help="Path to JSONL evaluation dataset.",
    )
    @click.option(
        "--metric",
        "-m",
        default="all",
        type=click.Choice(SUPPORTED_METRICS, case_sensitive=False),
        show_default=True,
        help="Metric to evaluate.",
    )
    @click.option(
        "--k",
        default=10,
        type=int,
        show_default=True,
        help="Cut-off K for Recall@K and nDCG@K.",
    )
    @click.option(
        "--output-format",
        "-o",
        default="text",
        type=click.Choice(["text", "json", "csv"], case_sensitive=False),
        show_default=True,
        help="Output format.",
    )
    @click.option(
        "--threshold",
        "-t",
        default=None,
        type=float,
        help="Override pass threshold (0.0–1.0). Uses per-metric defaults if not set.",
    )
    @click.option(
        "--save",
        "-s",
        default=None,
        type=click.Path(),
        help="Save results to this file path.",
    )
    @click.option(
        "--verbose",
        "-v",
        is_flag=True,
        default=False,
        help="Show per-record details.",
    )
    def run(
        dataset: str,
        metric: str,
        k: int,
        output_format: str,
        threshold: float | None,
        save: str | None,
        verbose: bool,
    ) -> None:
        """Run evaluation metric(s) against a dataset."""
        click.echo(f"Loading dataset: {dataset}", err=True)
        records = _load_dataset(dataset)
        click.echo(f"Loaded {len(records)} records.", err=True)

        results: dict[str, Any] = {}

        metrics_to_run = SUPPORTED_METRICS[:-1] if metric == "all" else [metric]

        for m in metrics_to_run:
            click.echo(f"Running: {m}...", err=True)
            try:
                result = _run_metric(m, records, k=k, threshold=threshold)
                results[m] = result
            except Exception as exc:
                click.echo(f"  ERROR running {m}: {exc}", err=True)
                results[m] = {"error": str(exc)}

        _output_results(results, output_format, verbose)

        if save:
            _save_results(results, save, output_format)
            click.echo(f"Results saved to: {save}", err=True)

    @cli.command()
    @click.option(
        "--dataset",
        "-d",
        required=True,
        type=click.Path(exists=True, readable=True),
        help="Path to JSONL evaluation dataset.",
    )
    def gate(dataset: str) -> None:
        """Run CI gate — exits with code 1 if any metric fails its threshold."""
        from evals.runners.ci_gate import run_ci_gate
        exit_code = run_ci_gate(dataset_path=dataset, output_format="text")
        sys.exit(exit_code)

    @cli.command()
    @click.argument("dataset", type=click.Path(exists=True, readable=True))
    def inspect(dataset: str) -> None:
        """Inspect a JSONL dataset — print field summary and first 3 records."""
        records = _load_dataset(dataset)
        if not records:
            click.echo("Dataset is empty.")
            return

        click.echo(f"Records: {len(records)}")
        if records:
            click.echo(f"Fields: {sorted(records[0].keys())}")
            click.echo("\nFirst 3 records:")
            for i, rec in enumerate(records[:3]):
                click.echo(f"\n  [{i+1}] {json.dumps(rec, indent=4, default=str)}")

    # ---------------------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------------------

    def _load_dataset(path: str) -> list[dict]:
        records: list[dict] = []
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        return records

    def _run_metric(
        metric_name: str,
        records: list[dict],
        k: int = 10,
        threshold: float | None = None,
    ) -> dict[str, Any]:
        """Dispatch to the appropriate metric function."""

        if metric_name == "recall_at_k":
            from evals.retrieval.recall_at_k import recall_at_k
            scores = [
                recall_at_k(
                    r.get("retrieval_results", {}).get("retrieved_ids", []),
                    r.get("retrieval_results", {}).get("relevant_ids", []),
                    k=k,
                )
                for r in records
                if r.get("retrieval_results", {}).get("relevant_ids")
            ]
            mean = sum(scores) / len(scores) if scores else 0.0
            th = threshold or 0.80
            return {"mean": round(mean, 4), "n": len(scores), "threshold": th, "pass": mean >= th}

        elif metric_name == "mrr":
            from evals.retrieval.mrr import reciprocal_rank
            scores = [
                reciprocal_rank(
                    r.get("retrieval_results", {}).get("retrieved_ids", []),
                    r.get("retrieval_results", {}).get("relevant_ids", []),
                )
                for r in records
                if r.get("retrieval_results", {}).get("relevant_ids")
            ]
            mean = sum(scores) / len(scores) if scores else 0.0
            th = threshold or 0.65
            return {"mean": round(mean, 4), "n": len(scores), "threshold": th, "pass": mean >= th}

        elif metric_name == "ndcg":
            from evals.retrieval.ndcg import ndcg_at_k
            scores = [
                ndcg_at_k(
                    r.get("retrieval_results", {}).get("retrieved_ids", []),
                    r.get("retrieval_results", {}).get("relevance_map", {}),
                    k=k,
                )
                for r in records
                if r.get("retrieval_results", {}).get("relevance_map")
            ]
            mean = sum(scores) / len(scores) if scores else 0.0
            th = threshold or 0.70
            return {"mean": round(mean, 4), "n": len(scores), "threshold": th, "pass": mean >= th}

        elif metric_name == "faithfulness":
            from evals.generation.faithfulness import evaluate_faithfulness, batch_faithfulness
            pairs = [
                {"answer": r.get("agent_answer", ""), "context_passages": r.get("context_passages", [])}
                for r in records
                if r.get("agent_answer") and r.get("context_passages")
            ]
            th = threshold or 0.90
            if not pairs:
                return {"mean_score": None, "n": 0, "note": "No records with agent_answer + context_passages"}
            result = batch_faithfulness(pairs, threshold=th)
            return {**result, "threshold": th}

        elif metric_name == "citation_accuracy":
            from evals.generation.citation_accuracy import batch_citation_accuracy
            pairs = [
                {"answer": r.get("agent_answer", ""), "retrieved_documents": r.get("retrieved_documents", [])}
                for r in records
                if r.get("agent_answer")
            ]
            th = threshold or 0.85
            if not pairs:
                return {"mean_accuracy": None, "n": 0, "note": "No records with agent_answer"}
            result = batch_citation_accuracy(pairs, threshold=th)
            return {**result, "threshold": th}

        elif metric_name == "refusal_correctness":
            from evals.generation.refusal_correctness import batch_refusal_correctness
            triples = [
                {
                    "id": r.get("id", str(i)),
                    "query": r.get("input", {}).get("description", ""),
                    "response": r.get("agent_answer", ""),
                    **({"category": r["query_category"]} if "query_category" in r else {}),
                }
                for i, r in enumerate(records)
                if r.get("agent_answer")
            ]
            th = threshold or 0.95
            if not triples:
                return {"accuracy": None, "n": 0, "note": "No records with agent_answer"}
            return batch_refusal_correctness(triples, threshold=th)

        else:
            return {"error": f"Metric '{metric_name}' not yet implemented in CLI runner"}

    def _output_results(
        results: dict[str, Any],
        output_format: str,
        verbose: bool,
    ) -> None:
        if output_format == "json":
            click.echo(json.dumps(results, indent=2, default=str))
        elif output_format == "csv":
            click.echo("metric,mean,threshold,pass,n")
            for metric, data in results.items():
                if isinstance(data, dict) and "error" not in data:
                    mean = data.get("mean") or data.get("mean_score") or data.get("mean_accuracy") or data.get("accuracy") or 0.0
                    th = data.get("threshold", 0.0)
                    passed = data.get("pass") or data.get("passes", False)
                    n = data.get("n", 0)
                    click.echo(f"{metric},{mean},{th},{passed},{n}")
        else:
            click.echo("\n" + "=" * 60)
            click.echo("Eval Results")
            click.echo("=" * 60)
            for metric, data in results.items():
                if "error" in data:
                    click.echo(f"\n  {metric}: ERROR — {data['error']}")
                    continue
                mean = data.get("mean") or data.get("mean_score") or data.get("mean_accuracy") or data.get("accuracy") or 0.0
                th = data.get("threshold", 0.0)
                passed = data.get("pass") or data.get("passes", False)
                status = "PASS" if passed else "FAIL"
                click.echo(f"\n  [{status}] {metric}")
                if mean is not None:
                    click.echo(f"         score: {mean:.4f} (threshold: {th:.4f})")
                if verbose and isinstance(data, dict):
                    for k, v in data.items():
                        if k not in ("mean", "mean_score", "mean_accuracy", "accuracy", "threshold", "pass", "passes", "results"):
                            click.echo(f"         {k}: {v}")
            click.echo("=" * 60 + "\n")

    def _save_results(
        results: dict[str, Any],
        path: str,
        output_format: str,
    ) -> None:
        save_path = Path(path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        with save_path.open("w", encoding="utf-8") as fh:
            json.dump(results, fh, indent=2, default=str)

    def main():
        cli()


if __name__ == "__main__":
    main()
