"""Security posture scoring endpoint for the AI Agent SOC platform."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Request, status

from api.schemas.posture import ComponentScore, PostureRating, PostureScore, PostureTrend

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/posture", tags=["posture"])

# Component weights must sum to 1.0
COMPONENT_WEIGHTS: dict[str, float] = {
    "identity": 0.20,
    "policy": 0.20,
    "runtime": 0.20,
    "supply_chain": 0.15,
    "sdlc": 0.15,
    "mesh": 0.10,
}

REPO_TO_COMPONENT: dict[str, str] = {
    "ai-agent-identity-governance": "identity",
    "ai-agent-policy-enforcement-runtime": "policy",
    "ai-agent-runtime-guardrails": "runtime",
    "ai-agent-supply-chain-security": "supply_chain",
    "ai-agent-sdlc-code-security": "sdlc",
    "ai-agent-multi-cloud-mesh": "mesh",
    "ai-agent-api-gateway-security": "policy",
    "ai-agent-data-privacy-compliance": "identity",
    "ai-agent-cost-governance": "runtime",
}


@router.get(
    "/score",
    response_model=PostureScore,
    status_code=status.HTTP_200_OK,
    summary="Get the organization-wide security posture score",
)
async def get_posture_score(request: Request) -> PostureScore:
    """
    Compute and return the organization-wide security posture score.

    Aggregates events from all 9 upstream repos over the past 24 hours.
    Score formula: 100 - (critical_weighted * 20 + high_weighted * 10 + medium_weighted * 5)
    Clamped to [0, 100].
    """
    opensearch = getattr(request.app.state, "opensearch_client", None)
    now = datetime.now(UTC)
    window_start = now - timedelta(hours=24)

    raw_counts = await _query_event_counts(opensearch, window_start, now)
    component_scores = _compute_component_scores(raw_counts)
    overall_score = _compute_overall_score(component_scores)
    overall_trend = _compute_trend(component_scores)
    active_incidents = await _count_active_incidents(request)

    return PostureScore(
        overall_score=round(overall_score, 2),
        rating=PostureScore.rating_from_score(overall_score),
        trend=overall_trend,
        component_scores=component_scores,
        timestamp=now,
        evaluation_window_hours=24,
        total_events_evaluated=sum(cs.event_count_24h for cs in component_scores),
        active_incidents=active_incidents,
        recommendations=_generate_recommendations(component_scores),
    )


async def _query_event_counts(
    opensearch: Any,
    window_start: datetime,
    window_end: datetime,
) -> dict[str, dict[str, int]]:
    """
    Query OpenSearch for event severity counts per source_repo.

    Returns a dict mapping component name → {CRITICAL: n, HIGH: n, MEDIUM: n, LOW: n, INFO: n}
    """
    if opensearch is None:
        return {}

    query = {
        "size": 0,
        "query": {
            "bool": {
                "filter": [
                    {
                        "range": {
                            "@timestamp": {
                                "gte": window_start.isoformat(),
                                "lte": window_end.isoformat(),
                            }
                        }
                    }
                ]
            }
        },
        "aggs": {
            "by_repo": {
                "terms": {"field": "source_repo.keyword", "size": 20},
                "aggs": {
                    "by_severity": {
                        "terms": {"field": "severity.keyword", "size": 10}
                    }
                },
            }
        },
    }

    try:
        result = opensearch.search(index="soc-events-*", body=query)
    except Exception as exc:
        logger.warning("OpenSearch query failed for posture scoring: %s", exc)
        return {}

    counts: dict[str, dict[str, int]] = {}
    for repo_bucket in result.get("aggregations", {}).get("by_repo", {}).get("buckets", []):
        repo = repo_bucket["key"]
        component = REPO_TO_COMPONENT.get(repo)
        if component is None:
            continue
        if component not in counts:
            counts[component] = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "INFO": 0}
        for sev_bucket in repo_bucket.get("by_severity", {}).get("buckets", []):
            sev = sev_bucket["key"]
            if sev in counts[component]:
                counts[component][sev] += sev_bucket["doc_count"]

    return counts


def _compute_component_scores(
    raw_counts: dict[str, dict[str, int]],
) -> list[ComponentScore]:
    """Compute per-component posture scores from raw event counts."""
    scores: list[ComponentScore] = []

    for component, weight in COMPONENT_WEIGHTS.items():
        counts = raw_counts.get(component, {})
        critical = counts.get("CRITICAL", 0)
        high = counts.get("HIGH", 0)
        medium = counts.get("MEDIUM", 0)
        low = counts.get("LOW", 0)
        info = counts.get("INFO", 0)

        total = critical + high + medium + low + info

        # Deduction formula: penalise by severity
        deduction = (critical * 20) + (high * 10) + (medium * 5) + (low * 2)
        # Normalise against a baseline of 100 events to avoid small volumes being over-penalised
        baseline = max(total, 100)
        raw_score = max(0.0, 100.0 - (deduction / baseline * 100))
        weighted = raw_score * weight

        trend = PostureTrend.STABLE
        if critical > 5 or high > 20:
            trend = PostureTrend.DEGRADING
        elif critical == 0 and high < 5:
            trend = PostureTrend.IMPROVING

        scores.append(
            ComponentScore(
                component=component,
                weight=weight,
                score=round(raw_score, 2),
                weighted_score=round(weighted, 2),
                critical_count=critical,
                high_count=high,
                medium_count=medium,
                low_count=low,
                event_count_24h=total,
                trend=trend,
            )
        )

    return scores


def _compute_overall_score(component_scores: list[ComponentScore]) -> float:
    """Aggregate component weighted scores into a single overall score."""
    total_weighted = sum(cs.weighted_score for cs in component_scores)
    # Normalise: sum of weights = 1.0, so overall = sum(score_i * weight_i) / sum(weight_i)
    total_weight = sum(cs.weight for cs in component_scores)
    if total_weight == 0:
        return 100.0
    return min(100.0, max(0.0, total_weighted / total_weight))


def _compute_trend(component_scores: list[ComponentScore]) -> PostureTrend:
    """Derive overall trend from component-level trends."""
    degrading = sum(1 for cs in component_scores if cs.trend == PostureTrend.DEGRADING)
    improving = sum(1 for cs in component_scores if cs.trend == PostureTrend.IMPROVING)
    if degrading > improving:
        return PostureTrend.DEGRADING
    elif improving > degrading:
        return PostureTrend.IMPROVING
    return PostureTrend.STABLE


def _generate_recommendations(component_scores: list[ComponentScore]) -> list[str]:
    """Generate actionable recommendations based on component scores."""
    recommendations: list[str] = []
    for cs in sorted(component_scores, key=lambda x: x.score):
        if cs.score < 60:
            recommendations.append(
                f"URGENT: {cs.component.replace('_', ' ').title()} posture is critical "
                f"({cs.critical_count} critical events in 24h). Immediate review required."
            )
        elif cs.score < 80:
            recommendations.append(
                f"WARN: {cs.component.replace('_', ' ').title()} shows elevated {cs.component} events. "
                f"Review {cs.high_count} high-severity findings."
            )
    if not recommendations:
        recommendations.append(
            "Security posture is within acceptable parameters. Continue monitoring."
        )
    return recommendations[:5]


async def _count_active_incidents(request: Request) -> int:
    """Count currently active (non-closed) incidents."""
    db = getattr(request.app.state, "db_pool", None)
    if db is None:
        return 0
    try:
        async with db.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT COUNT(*) AS cnt FROM incidents WHERE status NOT IN ('CLOSED', 'FALSE_POSITIVE')"
            )
            return int(row["cnt"]) if row else 0
    except Exception as exc:
        logger.warning("Failed to count active incidents: %s", exc)
        return 0
