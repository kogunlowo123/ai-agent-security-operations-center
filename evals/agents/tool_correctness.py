"""
Tool correctness evaluation for the SOC AI agent.

Evaluates whether the agent called the correct tools in the correct order
for a given security investigation query.

Metrics:
  - Tool Precision: fraction of tool calls that were appropriate
  - Tool Recall: fraction of necessary tools that were actually called
  - Tool F1: harmonic mean of precision and recall
  - Order Correctness: whether required tool dependencies were respected
  - Parameter Correctness: whether tool inputs matched expected values
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass
class ToolCall:
    """A single tool invocation by the agent."""

    tool_name: str
    inputs: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)
    step_index: int = 0

    def __repr__(self) -> str:
        return f"ToolCall({self.tool_name!r}, step={self.step_index})"


@dataclass
class ExpectedToolCall:
    """
    Specification of an expected tool call in the golden trajectory.

    Supports optional input matchers for flexible parameter validation.
    """

    tool_name: str
    required: bool = True
    input_matchers: dict[str, Callable[[Any], bool]] = field(default_factory=dict)
    must_come_after: list[str] = field(default_factory=list)  # tool names

    def matches_inputs(self, actual_inputs: dict[str, Any]) -> tuple[bool, list[str]]:
        """
        Check whether actual tool inputs satisfy all input matchers.

        Returns (all_pass, list_of_failures).
        """
        failures: list[str] = []
        for param_name, matcher in self.input_matchers.items():
            actual_value = actual_inputs.get(param_name)
            try:
                if not matcher(actual_value):
                    failures.append(
                        f"param '{param_name}': value {actual_value!r} did not satisfy matcher"
                    )
            except Exception as exc:
                failures.append(f"param '{param_name}': matcher raised {exc}")
        return len(failures) == 0, failures


@dataclass
class ToolCorrectnessResult:
    """Result of tool correctness evaluation for a single query."""

    query_id: str
    tool_precision: float
    tool_recall: float
    tool_f1: float
    order_correct: bool
    parameter_scores: dict[str, float]   # tool_name → parameter correctness [0,1]
    missing_tools: list[str]
    spurious_tools: list[str]
    parameter_failures: dict[str, list[str]]  # tool_name → list of failure messages

    @property
    def mean_parameter_correctness(self) -> float:
        """Mean parameter correctness across all checked tool calls."""
        scores = list(self.parameter_scores.values())
        return sum(scores) / len(scores) if scores else 1.0

    @property
    def overall_score(self) -> float:
        """
        Composite tool correctness score in [0.0, 1.0].

        Weights: F1 (0.4), order (0.3), parameter correctness (0.3)
        """
        order_score = 1.0 if self.order_correct else 0.0
        return (
            0.4 * self.tool_f1
            + 0.3 * order_score
            + 0.3 * self.mean_parameter_correctness
        )

    def __str__(self) -> str:
        return (
            f"ToolCorrectness[{self.query_id}]: "
            f"score={self.overall_score:.3f}, "
            f"P={self.tool_precision:.3f}, R={self.tool_recall:.3f}, "
            f"F1={self.tool_f1:.3f}, order={self.order_correct}, "
            f"params={self.mean_parameter_correctness:.3f}"
        )


def evaluate_tool_correctness(
    query_id: str,
    expected_tools: list[ExpectedToolCall],
    actual_calls: list[ToolCall],
) -> ToolCorrectnessResult:
    """
    Evaluate whether the agent called the correct tools for a query.

    Parameters
    ----------
    query_id:
        Identifier for the query/scenario.
    expected_tools:
        List of expected tool calls (golden specification).
    actual_calls:
        List of tool calls the agent actually made, in execution order.

    Returns
    -------
    ToolCorrectnessResult

    Examples
    --------
    >>> expected = [
    ...     ExpectedToolCall("mitre_rag_tool", required=True),
    ...     ExpectedToolCall("opensearch_query", required=True),
    ...     ExpectedToolCall("incident_create", required=False),
    ... ]
    >>> actual = [
    ...     ToolCall("mitre_rag_tool", step_index=0),
    ...     ToolCall("opensearch_query", step_index=1),
    ... ]
    >>> result = evaluate_tool_correctness("q1", expected, actual)
    >>> result.tool_recall  # all required tools were called
    1.0
    """
    actual_tool_names = [c.tool_name for c in actual_calls]
    actual_tool_set = set(actual_tool_names)

    required_tools = {e.tool_name for e in expected_tools if e.required}
    all_expected_tools = {e.tool_name for e in expected_tools}

    # --- Precision / Recall ---
    true_positives = actual_tool_set & all_expected_tools
    false_positives = actual_tool_set - all_expected_tools  # spurious
    false_negatives = required_tools - actual_tool_set     # missing required

    precision = len(true_positives) / len(actual_tool_set) if actual_tool_set else 1.0
    recall = len(true_positives) / len(required_tools) if required_tools else 1.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )

    # --- Order correctness ---
    order_correct = True
    for expected in expected_tools:
        if not expected.must_come_after:
            continue
        if expected.tool_name not in actual_tool_set:
            continue

        tool_index = next(
            (c.step_index for c in actual_calls if c.tool_name == expected.tool_name),
            None,
        )
        if tool_index is None:
            continue

        for predecessor in expected.must_come_after:
            pred_index = next(
                (c.step_index for c in actual_calls if c.tool_name == predecessor),
                None,
            )
            if pred_index is not None and pred_index >= tool_index:
                order_correct = False
                logger.warning(
                    "Query '%s': tool '%s' was called before required predecessor '%s'",
                    query_id,
                    expected.tool_name,
                    predecessor,
                )
                break

    # --- Parameter correctness ---
    parameter_scores: dict[str, float] = {}
    parameter_failures: dict[str, list[str]] = {}

    actual_calls_by_tool: dict[str, ToolCall] = {}
    for call in actual_calls:
        actual_calls_by_tool.setdefault(call.tool_name, call)

    for expected in expected_tools:
        if not expected.input_matchers:
            continue
        actual_call = actual_calls_by_tool.get(expected.tool_name)
        if actual_call is None:
            parameter_scores[expected.tool_name] = 0.0
            parameter_failures[expected.tool_name] = ["tool was not called"]
            continue

        passed, failures = expected.matches_inputs(actual_call.inputs)
        total_checks = len(expected.input_matchers)
        failed_checks = len(failures)
        score = (total_checks - failed_checks) / total_checks if total_checks > 0 else 1.0
        parameter_scores[expected.tool_name] = score
        if failures:
            parameter_failures[expected.tool_name] = failures

    return ToolCorrectnessResult(
        query_id=query_id,
        tool_precision=precision,
        tool_recall=recall,
        tool_f1=f1,
        order_correct=order_correct,
        parameter_scores=parameter_scores,
        missing_tools=list(false_negatives),
        spurious_tools=list(false_positives),
        parameter_failures=parameter_failures,
    )


def batch_evaluate_tool_correctness(
    samples: list[tuple[str, list[ExpectedToolCall], list[ToolCall]]],
) -> dict[str, Any]:
    """
    Evaluate tool correctness across multiple samples.

    Parameters
    ----------
    samples:
        List of (query_id, expected_tools, actual_calls) tuples.

    Returns
    -------
    dict with aggregate metrics and per-query results.
    """
    results = [
        evaluate_tool_correctness(qid, expected, actual)
        for qid, expected, actual in samples
    ]

    n = len(results)
    if n == 0:
        return {
            "results": [],
            "mean_score": 0.0,
            "mean_precision": 0.0,
            "mean_recall": 0.0,
            "mean_f1": 0.0,
            "order_correct_rate": 0.0,
            "mean_parameter_correctness": 0.0,
        }

    return {
        "results": results,
        "mean_score": sum(r.overall_score for r in results) / n,
        "mean_precision": sum(r.tool_precision for r in results) / n,
        "mean_recall": sum(r.tool_recall for r in results) / n,
        "mean_f1": sum(r.tool_f1 for r in results) / n,
        "order_correct_rate": sum(1 for r in results if r.order_correct) / n,
        "mean_parameter_correctness": sum(r.mean_parameter_correctness for r in results) / n,
    }
