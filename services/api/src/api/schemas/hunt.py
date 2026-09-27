"""Threat hunt schemas for the AI Agent SOC platform."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class HuntStatus(str, Enum):
    """Threat hunt job status."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class HuntType(str, Enum):
    """Type of threat hunt."""

    HYPOTHESIS = "HYPOTHESIS"
    IOC = "IOC"
    TECHNIQUE = "TECHNIQUE"
    ANOMALY = "ANOMALY"


class HuntRequest(BaseModel):
    """Request to launch a threat hunt."""

    hypothesis: str = Field(..., min_length=10, description="Hunt hypothesis to investigate")
    hunt_type: HuntType = HuntType.HYPOTHESIS
    mitre_technique: Optional[str] = Field(
        None, description="MITRE ATT&CK technique to hunt for, e.g. T1078"
    )
    iocs: list[str] = Field(
        default_factory=list,
        description="Indicators of compromise to search for",
    )
    time_range_hours: int = Field(
        default=24,
        ge=1,
        le=720,
        description="Look-back period in hours",
    )
    scope: Optional[str] = Field(
        None, description="Scope filter: tenant, environment, or specific agent"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "hypothesis": "AI agents are being used for privilege escalation via IAM role chaining",
                "hunt_type": "TECHNIQUE",
                "mitre_technique": "T1078",
                "iocs": [],
                "time_range_hours": 48,
                "scope": None,
            }
        }
    }


class HuntFinding(BaseModel):
    """Single finding from a threat hunt."""

    finding_id: str
    severity: str
    title: str
    description: str
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    mitre_techniques: list[str] = Field(default_factory=list)
    affected_principals: list[str] = Field(default_factory=list)
    timestamp: datetime
    raw_events: list[dict[str, Any]] = Field(default_factory=list)


class HuntJob(BaseModel):
    """Threat hunt job record."""

    hunt_id: str
    status: HuntStatus
    hypothesis: str
    hunt_type: HuntType
    submitted_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    findings_count: int = 0
    findings: list[HuntFinding] = Field(default_factory=list)
    siem_queries_executed: list[str] = Field(default_factory=list)
    error_message: Optional[str] = None
    report: Optional[str] = Field(None, description="AI-generated hunt report")


class HuntLaunchResult(BaseModel):
    """Response from launching a threat hunt."""

    hunt_id: str
    status: HuntStatus
    message: str
    estimated_completion_seconds: Optional[int] = None
