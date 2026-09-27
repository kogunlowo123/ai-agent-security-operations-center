"""CloudEvent ingestion endpoint for the AI Agent SOC platform."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Optional

import boto3
from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, HTTPException, Request, status
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from api.schemas.event import (
    CloudEventIngest,
    EventIngestionResult,
    EventSeverity,
    TriageStatus,
)

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

router = APIRouter(prefix="/events", tags=["events"])

# Severity → queue routing
SEVERITY_QUEUE_MAP: dict[EventSeverity, str] = {
    EventSeverity.CRITICAL: "triage-critical-queue",
    EventSeverity.HIGH: "triage-high-queue",
    EventSeverity.MEDIUM: "triage-medium-queue",
    EventSeverity.LOW: "triage-low-queue",
    EventSeverity.INFO: "triage-info-queue",
}


def _get_sqs_client(request: Request) -> boto3.client:
    return request.app.state.sqs_client


def _get_db(request: Request):
    return request.app.state.db_pool


@router.post(
    "/ingest",
    response_model=EventIngestionResult,
    status_code=status.HTTP_200_OK,
    summary="Ingest a CloudEvent from an upstream AI agent repository",
)
async def ingest_event(
    cloud_event: CloudEventIngest,
    request: Request,
) -> EventIngestionResult:
    """
    Accept a CloudEvents 1.0 envelope from any of the 9 upstream AI agent repositories.

    - Validates schema and event type
    - Routes to the appropriate SQS triage queue based on severity
    - Auto-creates an Incident record for CRITICAL severity events
    - Emits an OpenTelemetry span for observability
    """
    event_id = str(uuid.uuid4())

    with tracer.start_as_current_span("soc.event.ingest") as span:
        span.set_attribute("event.id", event_id)
        span.set_attribute("event.type", cloud_event.type)
        span.set_attribute("event.source", cloud_event.source)
        span.set_attribute("event.severity", cloud_event.data.severity.value)
        span.set_attribute("event.principal_id", cloud_event.data.principal_id)
        span.set_attribute("event.tenant_id", getattr(request.state, "tenant_id", "unknown"))

        try:
            incident_id: Optional[str] = None

            # Persist to OpenSearch SIEM
            await _index_to_siem(request, event_id, cloud_event)

            # Route to triage queue
            queue_url = await _route_to_queue(
                request,
                event_id,
                cloud_event,
            )
            span.set_attribute("sqs.queue_url", queue_url or "")

            # Auto-create incident for CRITICAL events
            if cloud_event.data.severity == EventSeverity.CRITICAL:
                incident_id = await _auto_create_incident(request, event_id, cloud_event)
                span.set_attribute("incident.id", incident_id or "")
                span.set_attribute("incident.auto_created", True)

            triage_status = (
                TriageStatus.ESCALATED
                if cloud_event.data.severity == EventSeverity.CRITICAL
                else TriageStatus.QUEUED
            )

            span.set_status(Status(StatusCode.OK))
            logger.info(
                "Event ingested",
                extra={
                    "event_id": event_id,
                    "severity": cloud_event.data.severity.value,
                    "triage_status": triage_status.value,
                    "incident_id": incident_id,
                },
            )

            return EventIngestionResult(
                event_id=event_id,
                triage_status=triage_status,
                incident_id=incident_id,
                message=f"Event {event_id} accepted for triage",
                span_id=format(span.get_span_context().span_id, "016x"),
            )

        except ClientError as exc:
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR, str(exc)))
            logger.error("SQS routing failed: %s", exc, extra={"event_id": event_id})
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Event queue temporarily unavailable. Please retry.",
            ) from exc
        except Exception as exc:
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR, str(exc)))
            logger.exception("Unexpected error during event ingestion: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal error during event ingestion.",
            ) from exc


async def _route_to_queue(
    request: Request,
    event_id: str,
    cloud_event: CloudEventIngest,
) -> Optional[str]:
    """Send the event to the appropriate SQS triage queue."""
    sqs: boto3.client = _get_sqs_client(request)
    if sqs is None:
        logger.warning("SQS client not initialized; skipping queue routing")
        return None

    queue_name = SEVERITY_QUEUE_MAP.get(cloud_event.data.severity, "triage-medium-queue")
    settings = request.app.state.settings

    try:
        queue_url = f"{settings.sqs_base_url}/{queue_name}"
        message_body = {
            "event_id": event_id,
            "specversion": cloud_event.specversion,
            "type": cloud_event.type,
            "source": cloud_event.source,
            "id": cloud_event.id,
            "time": cloud_event.time.isoformat(),
            "data": cloud_event.data.model_dump(),
        }
        sqs.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps(message_body, default=str),
            MessageAttributes={
                "severity": {
                    "StringValue": cloud_event.data.severity.value,
                    "DataType": "String",
                },
                "source_repo": {
                    "StringValue": cloud_event.data.source_repo,
                    "DataType": "String",
                },
            },
        )
        return queue_url
    except ClientError as exc:
        logger.error("Failed to send to SQS: %s", exc)
        raise


async def _index_to_siem(
    request: Request,
    event_id: str,
    cloud_event: CloudEventIngest,
) -> None:
    """Index the raw event into OpenSearch for SIEM correlation."""
    opensearch = getattr(request.app.state, "opensearch_client", None)
    if opensearch is None:
        return

    doc = {
        "@timestamp": cloud_event.time.isoformat(),
        "event_id": event_id,
        "event_type": cloud_event.type,
        "source": cloud_event.source,
        "cloud_event_id": cloud_event.id,
        "severity": cloud_event.data.severity.value,
        "principal_id": cloud_event.data.principal_id,
        "tier": cloud_event.data.tier,
        "source_repo": cloud_event.data.source_repo,
        "payload": cloud_event.data.payload,
        "tenant_id": getattr(request.state, "tenant_id", "unknown"),
        "ingested_at": datetime.now(UTC).isoformat(),
    }

    try:
        opensearch.index(
            index=f"soc-events-{datetime.now(UTC).strftime('%Y.%m')}",
            id=event_id,
            body=doc,
        )
    except Exception as exc:
        logger.warning("Failed to index event to OpenSearch: %s", exc)


async def _auto_create_incident(
    request: Request,
    event_id: str,
    cloud_event: CloudEventIngest,
) -> str:
    """Auto-create an incident record for CRITICAL severity events."""
    incident_id = f"INC-{uuid.uuid4().hex[:8].upper()}"
    db = _get_db(request)

    if db is None:
        logger.warning("Database pool not initialized; incident not persisted")
        return incident_id

    now = datetime.now(UTC)
    try:
        async with db.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO incidents (
                    id, title, description, severity, status,
                    tenant_id, principal_id, source_event_id,
                    source_repo, severity_score, created_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                ON CONFLICT (id) DO NOTHING
                """,
                incident_id,
                f"AUTO: {cloud_event.type} from {cloud_event.data.source_repo}",
                f"Critical event auto-escalated from {cloud_event.data.source_repo}. "
                f"Principal: {cloud_event.data.principal_id}. Event ID: {event_id}",
                "CRITICAL",
                "OPEN",
                getattr(request.state, "tenant_id", "default"),
                cloud_event.data.principal_id,
                event_id,
                cloud_event.data.source_repo,
                10.0,
                now,
                now,
            )
    except Exception as exc:
        logger.warning("Failed to persist auto-created incident: %s", exc)

    return incident_id
