"""LangGraph state definitions for SOC agent orchestration."""

from __future__ import annotations

from typing import Annotated, Any, Optional

from langgraph.graph.message import add_messages


class SOCAnalystState(dict):
    """
    State for the SOC Analyst LangGraph agent.

    Represents the mutable context flowing through each node
    of the triage and investigation workflow.
    """

    alert: dict[str, Any]
    retrieved_context: list[dict[str, Any]]
    mitre_tactics: list[str]
    mitre_techniques: list[str]
    similar_incidents: list[dict[str, Any]]
    analysis: str
    verdict: str  # TRUE_POSITIVE | FALSE_POSITIVE | ESCALATED
    citations: list[str]
    severity_score: float
    incident_id: Optional[str]
    messages: Annotated[list, add_messages]
    error: Optional[str]
    hop_count: int


class ThreatHunterState(dict):
    """
    State for the Threat Hunter LangGraph agent.

    Tracks the hypothesis, SIEM results, and final findings
    for a single threat hunt execution.
    """

    hunt_id: str
    hunt_hypothesis: str
    hunt_query: str
    siem_results: list[dict[str, Any]]
    mitre_alignment: list[dict[str, Any]]
    findings: list[dict[str, Any]]
    severity: str
    report: str
    messages: Annotated[list, add_messages]
    error: Optional[str]


class IncidentResponderState(dict):
    """
    State for the Incident Responder LangGraph agent.

    Manages the full incident response lifecycle from assignment
    through remediation and closure.
    """

    incident_id: str
    incident_data: dict[str, Any]
    timeline: list[dict[str, Any]]
    playbook: str
    remediation_steps: list[str]
    approval_required: bool
    approval_status: str  # PENDING | APPROVED | DENIED | TIMEOUT
    notifications_sent: list[str]
    messages: Annotated[list, add_messages]
    error: Optional[str]
