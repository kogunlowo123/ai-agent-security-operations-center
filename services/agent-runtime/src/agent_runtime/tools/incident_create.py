"""Incident creation tool for the SOC agent runtime."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)


class IncidentCreateTool:
    """
    Tool for creating and managing incident records.

    Persists incidents to PostgreSQL and returns the new incident ID.
    """

    def __init__(self, db_pool=None) -> None:
        self._db = db_pool

    async def create(
        self,
        alert: dict[str, Any],
        analysis: str,
        mitre_techniques: list[str],
        severity_score: float,
        verdict: str = "TRUE_POSITIVE",
        tenant_id: str = "default",
    ) -> str:
        """Create a standard incident record and return its ID."""
        incident_id = f"INC-{uuid.uuid4().hex[:8].upper()}"
        now = datetime.now(UTC)

        if self._db is None:
            logger.warning("DB pool not available; incident %s not persisted", incident_id)
            return incident_id

        severity = alert.get("severity", "HIGH")
        if severity_score >= 9.0:
            severity = "CRITICAL"
        elif severity_score >= 7.0:
            severity = "HIGH"
        elif severity_score >= 5.0:
            severity = "MEDIUM"
        else:
            severity = "LOW"

        try:
            async with self._db.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO incidents (
                        id, title, description, severity, status,
                        tenant_id, principal_id, source_event_id,
                        source_repo, analysis, verdict, severity_score,
                        created_at, updated_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    incident_id,
                    f"SOC: {alert.get('type', 'unknown')} from {alert.get('source_repo', 'unknown')}",
                    analysis[:2000] if analysis else "AI-generated incident",
                    severity,
                    "OPEN",
                    tenant_id,
                    alert.get("principal_id", "unknown"),
                    alert.get("id", "unknown"),
                    alert.get("source_repo", "unknown"),
                    analysis[:4000] if analysis else "",
                    verdict,
                    severity_score,
                    now,
                    now,
                )
        except Exception as exc:
            logger.error("Failed to create incident %s: %s", incident_id, exc)

        return incident_id

    async def create_critical(
        self,
        alert: dict[str, Any],
        analysis: str = "AUTO-ESCALATED: Critical severity detected",
        severity_score: float = 10.0,
        tenant_id: str = "default",
    ) -> str:
        """Create a critical incident with immediate escalation status."""
        return await self.create(
            alert=alert,
            analysis=analysis,
            mitre_techniques=[],
            severity_score=severity_score,
            verdict="ESCALATED",
            tenant_id=tenant_id,
        )

    async def update_with_mitre(
        self,
        incident_id: str,
        mitre_techniques: list[str],
        citations: list[str],
    ) -> None:
        """Update an existing incident with MITRE technique assignments and citations."""
        if self._db is None:
            return
        try:
            async with self._db.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE incidents
                    SET mitre_techniques = $1, citations = $2, updated_at = $3
                    WHERE id = $4
                    """,
                    mitre_techniques,
                    citations,
                    datetime.now(UTC),
                    incident_id,
                )
        except Exception as exc:
            logger.warning("Failed to update incident %s with MITRE data: %s", incident_id, exc)
