"""Security posture scoring schemas for the AI Agent SOC platform."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class PostureTrend(str, Enum):
    """Direction of posture score movement."""

    IMPROVING = "IMPROVING"
    DEGRADING = "DEGRADING"
    STABLE = "STABLE"


class PostureRating(str, Enum):
    """Overall posture rating category."""

    EXCELLENT = "EXCELLENT"
    GOOD = "GOOD"
    FAIR = "FAIR"
    POOR = "POOR"
    CRITICAL = "CRITICAL"


class ComponentScore(BaseModel):
    """Security posture score for a single component."""

    component: str
    weight: float = Field(ge=0.0, le=1.0)
    score: float = Field(ge=0.0, le=100.0)
    weighted_score: float = Field(ge=0.0, le=100.0)
    critical_count: int = Field(ge=0)
    high_count: int = Field(ge=0)
    medium_count: int = Field(ge=0)
    low_count: int = Field(ge=0)
    event_count_24h: int = Field(ge=0, description="Total events in the last 24 hours")
    trend: PostureTrend = PostureTrend.STABLE


class PostureScore(BaseModel):
    """Organization-wide security posture score."""

    overall_score: float = Field(ge=0.0, le=100.0, description="Weighted aggregate posture score")
    rating: PostureRating
    trend: PostureTrend
    component_scores: list[ComponentScore]
    timestamp: datetime
    evaluation_window_hours: int = Field(default=24)
    total_events_evaluated: int = Field(ge=0)
    active_incidents: int = Field(ge=0)
    recommendations: list[str] = Field(default_factory=list)
    previous_score: Optional[float] = Field(
        None, ge=0.0, le=100.0, description="Score at previous evaluation"
    )
    score_delta: Optional[float] = Field(
        None, description="Change from previous evaluation"
    )

    @classmethod
    def rating_from_score(cls, score: float) -> PostureRating:
        """Derive a rating category from a numeric score."""
        if score >= 90:
            return PostureRating.EXCELLENT
        elif score >= 75:
            return PostureRating.GOOD
        elif score >= 60:
            return PostureRating.FAIR
        elif score >= 40:
            return PostureRating.POOR
        else:
            return PostureRating.CRITICAL
