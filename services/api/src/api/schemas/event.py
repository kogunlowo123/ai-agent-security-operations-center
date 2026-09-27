"""CloudEvent ingestion schemas for the AI Agent SOC platform."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class EventSeverity(str, Enum):
    """Security event severity levels."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class TriageStatus(str, Enum):
    """Triage status after event ingestion."""

    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    TRIAGED = "TRIAGED"
    ESCALATED = "ESCALATED"
    CLOSED = "CLOSED"


UPSTREAM_REPOS = frozenset(
    [
        "ai-agent-identity-governance",
        "ai-agent-policy-enforcement-runtime",
        "ai-agent-supply-chain-security",
        "ai-agent-api-gateway-security",
        "ai-agent-runtime-guardrails",
        "ai-agent-multi-cloud-mesh",
        "ai-agent-data-privacy-compliance",
        "ai-agent-sdlc-code-security",
        "ai-agent-cost-governance",
    ]
)

EVENT_TYPE_MAP: dict[str, str] = {
    "ai-agent-identity-governance": "identity.access.violation",
    "ai-agent-policy-enforcement-runtime": "policy.enforcement.breach",
    "ai-agent-supply-chain-security": "supply_chain.integrity.failure",
    "ai-agent-api-gateway-security": "gateway.abuse.detected",
    "ai-agent-runtime-guardrails": "runtime.guardrail.triggered",
    "ai-agent-multi-cloud-mesh": "mesh.anomaly.detected",
    "ai-agent-data-privacy-compliance": "privacy.violation.detected",
    "ai-agent-sdlc-code-security": "sdlc.vulnerability.found",
    "ai-agent-cost-governance": "cost.anomaly.detected",
}


class CloudEventData(BaseModel):
    """Payload data embedded within a CloudEvent."""

    principal_id: str = Field(..., description="Identity of the AI agent or user")
    tier: str = Field(..., pattern="^T[123]$", description="Agent tier (T1, T2, T3)")
    severity: EventSeverity = Field(..., description="Event severity level")
    source_repo: str = Field(..., description="Originating upstream repository")
    payload: dict[str, Any] = Field(default_factory=dict, description="Raw event payload")
    mitre_technique_hint: Optional[str] = Field(
        None, description="Optional MITRE technique hint from upstream"
    )

    @field_validator("source_repo")
    @classmethod
    def validate_source_repo(cls, v: str) -> str:
        if v not in UPSTREAM_REPOS:
            raise ValueError(
                f"source_repo '{v}' is not a recognized upstream repository. "
                f"Allowed: {sorted(UPSTREAM_REPOS)}"
            )
        return v


class CloudEventIngest(BaseModel):
    """CloudEvents 1.0 specification envelope for security event ingestion."""

    specversion: str = Field(..., pattern="^1\\.0$", description="CloudEvents spec version")
    type: str = Field(..., min_length=1, description="Event type identifier")
    source: str = Field(..., min_length=1, description="Event source URI")
    id: str = Field(..., min_length=1, description="Unique event identifier")
    time: datetime = Field(..., description="Event timestamp (ISO 8601)")
    datacontenttype: str = Field(
        default="application/json", description="Media type of the data"
    )
    data: CloudEventData = Field(..., description="Event-specific data payload")

    @field_validator("type")
    @classmethod
    def validate_event_type(cls, v: str) -> str:
        known_types = set(EVENT_TYPE_MAP.values())
        if v not in known_types:
            raise ValueError(
                f"Unknown event type '{v}'. "
                f"Expected one of: {sorted(known_types)}"
            )
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "specversion": "1.0",
                "type": "identity.access.violation",
                "source": "ai-agent-identity-governance/v1",
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "time": "2024-01-15T10:30:00Z",
                "datacontenttype": "application/json",
                "data": {
                    "principal_id": "agent-soc-analyst-001",
                    "tier": "T1",
                    "severity": "CRITICAL",
                    "source_repo": "ai-agent-identity-governance",
                    "payload": {
                        "violation_type": "privilege_escalation",
                        "target_resource": "arn:aws:iam::123456789012:role/AdminRole",
                    },
                },
            }
        }
    }


class EventIngestionResult(BaseModel):
    """Response returned after successful event ingestion."""

    event_id: str = Field(..., description="Unique identifier assigned to the ingested event")
    triage_status: TriageStatus = Field(..., description="Current triage status")
    incident_id: Optional[str] = Field(
        None, description="Incident ID if auto-created for CRITICAL events"
    )
    message: str = Field(..., description="Human-readable status message")
    queue_depth: Optional[int] = Field(
        None, description="Current triage queue depth"
    )
    span_id: Optional[str] = Field(
        None, description="OpenTelemetry span ID for correlation"
    )
