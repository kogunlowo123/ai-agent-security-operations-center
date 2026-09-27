"""
Agent trajectory evaluation for the SOC AI agent.

Compares actual agent action sequences (trajectories) to expected sequences
defined in golden datasets. Measures:

  - Exact Match: agent took the exact same steps in the exact same order
  - Prefix Match: agent trajectory starts with the expected steps
  - Step Coverage: fraction of expected steps that appear anywhere in the trajectory
  - Order Fidelity: how well the relative ordering of steps is preserved (Kendall's tau)
  - Spurious Action Rate: fraction of agent steps that are not in the expected set
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Sequence

logger = logging.getLogger(__name__)


@dataclass
class AgentStep:
    """A single step taken by the agent."""

    step_id: str
    action: str               # e.g., "retrieve_mitre_technique"
    tool: str                 # e.g., "mitre_rag_tool"
    inputs: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0    # Unix epoch

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, AgentStep):
            return NotImplemented
        return self.action == other.action and self.tool == other.tool

    def __hash__(self) -> int:
        return hash((self.action, self.tool))

    def __repr__(self) -> str:
        return f"AgentStep(action={self.action!r}, tool={self.tool!r})"


@dataclass
class TrajectoryEvalResult:
    """Result of comparing an actual trajectory to an expected trajectory."""

    query_id: str
    exact_match: bool
    prefix_match: bool
    step_coverage: float         # [0.0, 1.0]
    order_fidelity: float        # Kendall's tau ∈ [-1.0, 1.0], clamped to [0.0, 1.0]
    spurious_action_rate: float  # [0.0, 1.0]
    expected_steps: list[str]    # action names
    actual_steps: list[str]      # action names
    missing_steps: list[str]
    extra_steps: list[str]

    @property
    def overall_score(self) -> float:
        """
        Composite trajectory quality score in [0.0, 1.0].

        Weights: step_coverage (0.4), order_fidelity (0.3),
                 (1 - spurious_action_rate) (0.3)
        """
        return (
            0.4 * self.step_coverage
            + 0.3 * self.order_fidelity
            + 0.3 * (1.0 - self.spurious_action_rate)
        )

    def __str__(self) -> str:
        return (
            f"Trajectory[{self.query_id}]: score={self.overall_score:.3f}, "
            f"exact={self.exact_match}, coverage={self.step_coverage:.3f}, "
            f"order={self.order_fidelity:.3f}, spurious={self.spurious_action_rate:.3f}"
        )


def _step_actions(steps: Sequence[AgentStep]) -> list[str]:
    """Extract action names from a step sequence."""
    return [s.action for s in steps]


def _kendalls_tau(seq_a: list[str], seq_b: list[str]) -> float:
    """
    Compute a simplified Kendall's tau between two sequences of action names.

    Only considers elements that appear in BOTH sequences (their intersection).
    Returns a value in [-1, 1]; we clamp to [0, 1] for the fidelity metric.

    Parameters
    ----------
    seq_a, seq_b:
        Two ordered sequences of action names.

    Returns
    -------
    float
        Order fidelity in [0.0, 1.0].
    """
    common = [a for a in seq_a if a in set(seq_b)]
    if len(common) <= 1:
        return 1.0  # trivially ordered

    # Build position mapping in seq_b for common elements
    pos_b: dict[str, int] = {}
    for i, action in enumerate(seq_b):
        if action in set(common) and action not in pos_b:
            pos_b[action] = i

    # Count concordant vs discordant pairs using the order in seq_a
    concordant = 0
    discordant = 0
    for i in range(len(common)):
        for j in range(i + 1, len(common)):
            rank_i = pos_b.get(common[i], 0)
            rank_j = pos_b.get(common[j], 0)
            if rank_i < rank_j:
                concordant += 1
            elif rank_i > rank_j:
                discordant += 1

    total_pairs = concordant + discordant
    if total_pairs == 0:
        return 1.0

    tau = (concordant - discordant) / total_pairs
    # Clamp to [0, 1]: negative tau means completely reversed order
    return max(0.0, tau)


def evaluate_trajectory(
    query_id: str,
    expected: Sequence[AgentStep],
    actual: Sequence[AgentStep],
) -> TrajectoryEvalResult:
    """
    Compare an actual agent trajectory to an expected (golden) trajectory.

    Parameters
    ----------
    query_id:
        Identifier for the query/scenario being evaluated.
    expected:
        Golden trajectory — the sequence of steps the agent should take.
    actual:
        The sequence of steps the agent actually took.

    Returns
    -------
    TrajectoryEvalResult
        Detailed trajectory comparison metrics.

    Examples
    --------
    >>> expected = [
    ...     AgentStep("e1", "retrieve_mitre", "mitre_rag"),
    ...     AgentStep("e2", "search_incidents", "db_tool"),
    ...     AgentStep("e3", "generate_report", "report_tool"),
    ... ]
    >>> actual = [
    ...     AgentStep("a1", "retrieve_mitre", "mitre_rag"),
    ...     AgentStep("a2", "search_incidents", "db_tool"),
    ...     AgentStep("a3", "generate_report", "report_tool"),
    ... ]
    >>> result = evaluate_trajectory("q1", expected, actual)
    >>> result.exact_match
    True
    """
    expected_actions = _step_actions(expected)
    actual_actions = _step_actions(actual)
    expected_set = set(expected_actions)
    actual_set = set(actual_actions)

    # Exact match: same actions in same order
    exact_match = expected_actions == actual_actions

    # Prefix match: actual starts with expected
    prefix_match = actual_actions[: len(expected_actions)] == expected_actions

    # Step coverage: fraction of expected steps found anywhere in actual
    covered = expected_set & actual_set
    step_coverage = len(covered) / len(expected_set) if expected_set else 1.0

    # Order fidelity
    order_fidelity = _kendalls_tau(expected_actions, actual_actions)

    # Spurious actions: steps in actual not in expected
    spurious = [a for a in actual_actions if a not in expected_set]
    spurious_action_rate = len(spurious) / len(actual_actions) if actual_actions else 0.0

    missing_steps = [a for a in expected_actions if a not in actual_set]
    extra_steps = spurious

    return TrajectoryEvalResult(
        query_id=query_id,
        exact_match=exact_match,
        prefix_match=prefix_match,
        step_coverage=step_coverage,
        order_fidelity=order_fidelity,
        spurious_action_rate=spurious_action_rate,
        expected_steps=expected_actions,
        actual_steps=actual_actions,
        missing_steps=missing_steps,
        extra_steps=extra_steps,
    )


def batch_evaluate_trajectories(
    samples: list[tuple[str, Sequence[AgentStep], Sequence[AgentStep]]],
) -> dict[str, Any]:
    """
    Evaluate multiple trajectory comparisons and return aggregate statistics.

    Parameters
    ----------
    samples:
        List of (query_id, expected_trajectory, actual_trajectory) tuples.

    Returns
    -------
    dict with:
        - results: list of TrajectoryEvalResult
        - mean_score: mean overall score across all samples
        - exact_match_rate: fraction with exact match
        - mean_step_coverage: mean step coverage
        - mean_order_fidelity: mean order fidelity
        - mean_spurious_rate: mean spurious action rate
    """
    results = [
        evaluate_trajectory(qid, expected, actual)
        for qid, expected, actual in samples
    ]

    n = len(results)
    if n == 0:
        return {
            "results": [],
            "mean_score": 0.0,
            "exact_match_rate": 0.0,
            "mean_step_coverage": 0.0,
            "mean_order_fidelity": 0.0,
            "mean_spurious_rate": 0.0,
        }

    return {
        "results": results,
        "mean_score": sum(r.overall_score for r in results) / n,
        "exact_match_rate": sum(1 for r in results if r.exact_match) / n,
        "mean_step_coverage": sum(r.step_coverage for r in results) / n,
        "mean_order_fidelity": sum(r.order_fidelity for r in results) / n,
        "mean_spurious_rate": sum(r.spurious_action_rate for r in results) / n,
    }
