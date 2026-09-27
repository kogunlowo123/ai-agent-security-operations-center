"""Incident management endpoints for the AI Agent SOC platform."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request, status

from api.schemas.incident import (
    Incident,
    IncidentListResponse,
    IncidentSeverity,
    IncidentStatus,
    IncidentUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/incidents", tags=["incidents"])


@router.get(
    "",
    response_model=IncidentListResponse,
    status_code=status.HTTP_200_OK,
    summary="List active incidents with optional filters",
)
async def list_incidents(
    request: Request,
    incident_status: Optional[IncidentStatus] = Query(None, alias="status"),
    severity: Optional[IncidentSeverity] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
) -> IncidentListResponse:
    """Return a paginated list of incidents filtered by status and severity."""
    db = getattr(request.app.state, "db_pool", None)
    tenant_id = getattr(request.state, "tenant_id", "default")

    if db is None:
        return IncidentListResponse(
            items=[], total=0, page=page, page_size=page_size, has_more=False
        )

    offset = (page - 1) * page_size

    where_clauses = ["tenant_id = $1"]
    params: list = [tenant_id]
    param_idx = 2

    if incident_status is not None:
        where_clauses.append(f"status = ${param_idx}")
        params.append(incident_status.value)
        param_idx += 1

    if severity is not None:
        where_clauses.append(f"severity = ${param_idx}")
        params.append(severity.value)
        param_idx += 1

    where_sql = " AND ".join(where_clauses)

    try:
        async with db.acquire() as conn:
            total_row = await conn.fetchrow(
                f"SELECT COUNT(*) AS cnt FROM incidents WHERE {where_sql}",
                *params,
            )
            total = int(total_row["cnt"]) if total_row else 0

            rows = await conn.fetch(
                f"""
                SELECT * FROM incidents
                WHERE {where_sql}
                ORDER BY created_at DESC
                LIMIT ${param_idx} OFFSET ${param_idx + 1}
                """,
                *params,
                page_size,
                offset,
            )
    except Exception as exc:
        logger.exception("Failed to list incidents: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve incidents.",
        ) from exc

    items = [_row_to_incident(row) for row in rows]
    return IncidentListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_more=(page * page_size) < total,
    )


@router.get(
    "/{incident_id}",
    response_model=Incident,
    status_code=status.HTTP_200_OK,
    summary="Get a single incident by ID",
)
async def get_incident(incident_id: str, request: Request) -> Incident:
    """Retrieve a single incident record by its unique ID."""
    db = getattr(request.app.state, "db_pool", None)
    tenant_id = getattr(request.state, "tenant_id", "default")

    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available.",
        )

    try:
        async with db.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM incidents WHERE id = $1 AND tenant_id = $2",
                incident_id,
                tenant_id,
            )
    except Exception as exc:
        logger.exception("Failed to fetch incident %s: %s", incident_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve incident.",
        ) from exc

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident '{incident_id}' not found.",
        )

    return _row_to_incident(row)


@router.patch(
    "/{incident_id}",
    response_model=Incident,
    status_code=status.HTTP_200_OK,
    summary="Update an incident's status, assignee, or tags",
)
async def update_incident(
    incident_id: str,
    update: IncidentUpdate,
    request: Request,
) -> Incident:
    """Partially update an incident record."""
    db = getattr(request.app.state, "db_pool", None)
    tenant_id = getattr(request.state, "tenant_id", "default")

    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available.",
        )

    set_clauses: list[str] = []
    params: list = []
    param_idx = 1

    if update.status is not None:
        set_clauses.append(f"status = ${param_idx}")
        params.append(update.status.value)
        param_idx += 1

    if update.assignee is not None:
        set_clauses.append(f"assignee = ${param_idx}")
        params.append(update.assignee)
        param_idx += 1

    if update.tags is not None:
        set_clauses.append(f"tags = ${param_idx}")
        params.append(update.tags)
        param_idx += 1

    if update.remediation_steps is not None:
        set_clauses.append(f"remediation_steps = ${param_idx}")
        params.append(update.remediation_steps)
        param_idx += 1

    if not set_clauses:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No fields provided to update.",
        )

    set_clauses.append(f"updated_at = ${param_idx}")
    params.append(datetime.now(UTC))
    param_idx += 1

    # Append WHERE clause params
    params.extend([incident_id, tenant_id])
    set_sql = ", ".join(set_clauses)

    try:
        async with db.acquire() as conn:
            row = await conn.fetchrow(
                f"""
                UPDATE incidents
                SET {set_sql}
                WHERE id = ${param_idx} AND tenant_id = ${param_idx + 1}
                RETURNING *
                """,
                *params,
            )
    except Exception as exc:
        logger.exception("Failed to update incident %s: %s", incident_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update incident.",
        ) from exc

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident '{incident_id}' not found.",
        )

    return _row_to_incident(row)


def _row_to_incident(row: dict) -> Incident:
    """Convert a database row to an Incident schema object."""
    return Incident(
        id=row["id"],
        title=row["title"],
        description=row["description"],
        severity=IncidentSeverity(row["severity"]),
        status=IncidentStatus(row["status"]),
        tenant_id=row["tenant_id"],
        principal_id=row["principal_id"],
        source_event_id=row["source_event_id"],
        source_repo=row.get("source_repo", ""),
        mitre_techniques=row.get("mitre_techniques") or [],
        analysis=row.get("analysis"),
        verdict=row.get("verdict"),
        citations=row.get("citations") or [],
        severity_score=float(row.get("severity_score", 0.0)),
        assignee=row.get("assignee"),
        timeline=row.get("timeline") or [],
        remediation_steps=row.get("remediation_steps") or [],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        resolved_at=row.get("resolved_at"),
        tags=row.get("tags") or [],
        metadata=row.get("metadata") or {},
    )
