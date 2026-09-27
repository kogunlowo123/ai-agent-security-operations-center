"""Threat hunt management endpoints for the AI Agent SOC platform."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime

import boto3
from botocore.exceptions import ClientError
from fastapi import APIRouter, HTTPException, Request, status

from api.schemas.hunt import (
    HuntJob,
    HuntLaunchResult,
    HuntRequest,
    HuntStatus,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/hunt", tags=["threat-hunting"])


@router.post(
    "/launch",
    response_model=HuntLaunchResult,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Launch an AI-powered threat hunt",
)
async def launch_hunt(hunt_request: HuntRequest, request: Request) -> HuntLaunchResult:
    """
    Launch a threat hunt job.

    The hunt is submitted to the SQS hunt-queue and executed asynchronously
    by the threat-hunter LangGraph agent.
    """
    hunt_id = f"HUNT-{uuid.uuid4().hex[:12].upper()}"
    sqs: boto3.client = getattr(request.app.state, "sqs_client", None)
    settings = request.app.state.settings

    message_body = {
        "hunt_id": hunt_id,
        "hypothesis": hunt_request.hypothesis,
        "hunt_type": hunt_request.hunt_type.value,
        "mitre_technique": hunt_request.mitre_technique,
        "iocs": hunt_request.iocs,
        "time_range_hours": hunt_request.time_range_hours,
        "scope": hunt_request.scope,
        "submitted_at": datetime.now(UTC).isoformat(),
        "tenant_id": getattr(request.state, "tenant_id", "default"),
        "principal_id": getattr(request.state, "principal_id", "unknown"),
    }

    if sqs is not None:
        try:
            queue_url = f"{settings.sqs_base_url}/hunt-queue"
            sqs.send_message(
                QueueUrl=queue_url,
                MessageBody=json.dumps(message_body, default=str),
                MessageAttributes={
                    "hunt_id": {
                        "StringValue": hunt_id,
                        "DataType": "String",
                    },
                    "hunt_type": {
                        "StringValue": hunt_request.hunt_type.value,
                        "DataType": "String",
                    },
                },
            )
            logger.info("Hunt %s submitted to queue", hunt_id)
        except ClientError as exc:
            logger.error("Failed to submit hunt to SQS: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Hunt queue temporarily unavailable. Please retry.",
            ) from exc
    else:
        logger.warning("SQS client not available; hunt %s queued locally only", hunt_id)

    # Persist hunt job record
    await _persist_hunt_job(request, hunt_id, hunt_request)

    return HuntLaunchResult(
        hunt_id=hunt_id,
        status=HuntStatus.PENDING,
        message=f"Threat hunt {hunt_id} submitted for execution",
        estimated_completion_seconds=hunt_request.time_range_hours * 10,
    )


@router.get(
    "/{hunt_id}",
    response_model=HuntJob,
    status_code=status.HTTP_200_OK,
    summary="Get the status of a threat hunt",
)
async def get_hunt(hunt_id: str, request: Request) -> HuntJob:
    """Retrieve the current status and metadata of a threat hunt job."""
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
                "SELECT * FROM hunt_jobs WHERE hunt_id = $1 AND tenant_id = $2",
                hunt_id,
                tenant_id,
            )
    except Exception as exc:
        logger.exception("Failed to fetch hunt %s: %s", hunt_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve hunt job.",
        ) from exc

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Hunt job '{hunt_id}' not found.",
        )

    return HuntJob(
        hunt_id=row["hunt_id"],
        status=HuntStatus(row["status"]),
        hypothesis=row["hypothesis"],
        hunt_type=row["hunt_type"],
        submitted_at=row["submitted_at"],
        started_at=row.get("started_at"),
        completed_at=row.get("completed_at"),
        findings_count=row.get("findings_count", 0),
        findings=row.get("findings") or [],
        siem_queries_executed=row.get("siem_queries_executed") or [],
        error_message=row.get("error_message"),
        report=row.get("report"),
    )


@router.get(
    "/{hunt_id}/results",
    response_model=HuntJob,
    status_code=status.HTTP_200_OK,
    summary="Get the full results of a completed threat hunt",
)
async def get_hunt_results(hunt_id: str, request: Request) -> HuntJob:
    """Retrieve the full findings of a completed threat hunt."""
    hunt_job = await get_hunt(hunt_id, request)
    if hunt_job.status not in (HuntStatus.COMPLETED, HuntStatus.FAILED):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Hunt '{hunt_id}' is not yet complete (status: {hunt_job.status.value}).",
        )
    return hunt_job


async def _persist_hunt_job(
    request: Request,
    hunt_id: str,
    hunt_request: HuntRequest,
) -> None:
    """Persist a newly created hunt job record to the database."""
    db = getattr(request.app.state, "db_pool", None)
    if db is None:
        return

    try:
        async with db.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO hunt_jobs (
                    hunt_id, tenant_id, hypothesis, hunt_type,
                    mitre_technique, iocs, time_range_hours, status, submitted_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (hunt_id) DO NOTHING
                """,
                hunt_id,
                getattr(request.state, "tenant_id", "default"),
                hunt_request.hypothesis,
                hunt_request.hunt_type.value,
                hunt_request.mitre_technique,
                hunt_request.iocs,
                hunt_request.time_range_hours,
                HuntStatus.PENDING.value,
                datetime.now(UTC),
            )
    except Exception as exc:
        logger.warning("Failed to persist hunt job %s: %s", hunt_id, exc)
