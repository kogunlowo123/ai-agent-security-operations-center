"""Incident lifecycle schemas for the AI Agent SOC platform."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class IncidentStatus(str, Enum):
    """Incident lifecycle states."""

    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    REMEDIATED = "REMEDIATED"
    CLOSED = "CLOSED"
    FALSE_POSITIVE = "FALSE_POSITIVE"


class IncidentSeverity(str, Enum):
    """Incident severity classification."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class MitreTechnique(BaseModel):
    """MITRE ATT&CK technique reference."""

    technique_id: str = Field(..., description="ATT&CK technique ID, e.g. T1078")
    tactic: str = Field(..., description="Parent tactic name")
    name: str = Field(..., description="Technique name")
    description: Optional[str] = Field(None, description="Brief description")
    url: Optional[str] = Field(None, description="Link to ATT&CK technique page")


class IncidentTimeline(BaseModel):
    """Single timeline entry for an incident."""

    timestamp: datetime
    actor: str = Field(..., description="Who/what performed the action")
    action: str
    details: Optional[dict[str, Any]] = None


class Incident(BaseModel):
    """Full incident record."""

    id: str = Field(..., description="Unique incident identifier")
    title: str
    description: str
    severity: IncidentSeverity
    status: IncidentStatus = IncidentStatus.OPEN
    tenant_id: str
    principal_id: str
    source_event_id: str = Field(..., description="Original triggering event ID")
    source_repo: str
    mitre_techniques: list[MitreTechnique] = Field(default_factory=list)
    analysis: Optional[str] = Field(None, description="SOC analyst AI-generated analysis")
    verdict: Optional[str] = Field(None, description="TRUE_POSITIVE, FALSE_POSITIVE, ESCALATED")
    citations: list[str] = Field(default_factory=list, description="RAG source citations")
    severity_score: float = Field(ge=0.0, le=10.0, description="Numeric severity score 0-10")
    assignee: Optional[str] = None
    timeline: list[IncidentTimeline] = Field(default_factory=list)
    remediation_steps: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class IncidentListResponse(BaseModel):
    """Paginated list of incidents."""

    items: list[Incident]
    total: int
    page: int
    page_size: int
    has_more: bool


class IncidentUpdate(BaseModel):
    """Partial update for an incident record."""

    status: Optional[IncidentStatus] = None
    assignee: Optional[str] = None
    tags: Optional[list[str]] = None
    remediation_steps: Optional[list[str]] = None
    notes: Optional[str] = None
