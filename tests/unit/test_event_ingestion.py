"""Unit tests for the CloudEvent ingestion endpoint."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.conftest import CRITICAL_CLOUD_EVENT, VALID_CLOUD_EVENT, make_jwt


@pytest.mark.asyncio
async def test_valid_cloudevent_returns_200_with_event_id(client: AsyncClient) -> None:
    """A valid CloudEvent should return HTTP 200 with an event_id."""
    token = make_jwt()
    response = await client.post(
        "/api/v1/events/ingest",
        json=VALID_CLOUD_EVENT,
        headers={"Authorization": f"Bearer {token}", "X-Tenant-ID": "tenant-test"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "event_id" in body
    assert body["event_id"]
    assert body["triage_status"] == "QUEUED"
    assert body["incident_id"] is None


@pytest.mark.asyncio
async def test_critical_event_returns_incident_id(client: AsyncClient, mock_db_pool) -> None:
    """A CRITICAL severity CloudEvent should auto-create an incident."""
    _, mock_conn = mock_db_pool
    token = make_jwt()
    response = await client.post(
        "/api/v1/events/ingest",
        json=CRITICAL_CLOUD_EVENT,
        headers={"Authorization": f"Bearer {token}", "X-Tenant-ID": "tenant-test"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["triage_status"] == "ESCALATED"
    assert body["incident_id"] is not None
    assert body["incident_id"].startswith("INC-")


@pytest.mark.asyncio
async def test_missing_specversion_returns_422(client: AsyncClient) -> None:
    """CloudEvent missing specversion field should return HTTP 422."""
    token = make_jwt()
    invalid_event = {k: v for k, v in VALID_CLOUD_EVENT.items() if k != "specversion"}
    response = await client.post(
        "/api/v1/events/ingest",
        json=invalid_event,
        headers={"Authorization": f"Bearer {token}", "X-Tenant-ID": "tenant-test"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_wrong_specversion_returns_422(client: AsyncClient) -> None:
    """CloudEvent with specversion != 1.0 should return HTTP 422."""
    token = make_jwt()
    event = {**VALID_CLOUD_EVENT, "specversion": "2.0"}
    response = await client.post(
        "/api/v1/events/ingest",
        json=event,
        headers={"Authorization": f"Bearer {token}", "X-Tenant-ID": "tenant-test"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_unknown_event_type_returns_422(client: AsyncClient) -> None:
    """CloudEvent with an unknown type should return HTTP 422."""
    token = make_jwt()
    event = {**VALID_CLOUD_EVENT, "type": "unknown.event.type"}
    response = await client.post(
        "/api/v1/events/ingest",
        json=event,
        headers={"Authorization": f"Bearer {token}", "X-Tenant-ID": "tenant-test"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_unknown_source_repo_returns_422(client: AsyncClient) -> None:
    """CloudEvent with an unrecognized source_repo should return HTTP 422."""
    token = make_jwt()
    event = {
        **VALID_CLOUD_EVENT,
        "data": {
            **VALID_CLOUD_EVENT["data"],
            "source_repo": "not-a-real-repo",
        },
    }
    response = await client.post(
        "/api/v1/events/ingest",
        json=event,
        headers={"Authorization": f"Bearer {token}", "X-Tenant-ID": "tenant-test"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_missing_auth_header_returns_401(client: AsyncClient) -> None:
    """Requests without Authorization header should return HTTP 401."""
    response = await client.post(
        "/api/v1/events/ingest",
        json=VALID_CLOUD_EVENT,
        headers={"X-Tenant-ID": "tenant-test"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_health_endpoint_returns_200_without_auth(client: AsyncClient) -> None:
    """Health endpoint should not require authentication."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_event_id_is_unique_per_request(client: AsyncClient) -> None:
    """Each event ingest should produce a unique event_id."""
    token = make_jwt()
    headers = {"Authorization": f"Bearer {token}", "X-Tenant-ID": "tenant-test"}

    response1 = await client.post("/api/v1/events/ingest", json=VALID_CLOUD_EVENT, headers=headers)
    response2 = await client.post("/api/v1/events/ingest", json=VALID_CLOUD_EVENT, headers=headers)

    assert response1.status_code == 200
    assert response2.status_code == 200
    assert response1.json()["event_id"] != response2.json()["event_id"]


@pytest.mark.asyncio
async def test_info_event_returns_queued_status(client: AsyncClient) -> None:
    """INFO severity events should be queued, not escalated."""
    token = make_jwt()
    event = {
        **VALID_CLOUD_EVENT,
        "type": "cost.anomaly.detected",
        "data": {
            **VALID_CLOUD_EVENT["data"],
            "severity": "INFO",
            "source_repo": "ai-agent-cost-governance",
        },
    }
    response = await client.post(
        "/api/v1/events/ingest",
        json=event,
        headers={"Authorization": f"Bearer {token}", "X-Tenant-ID": "tenant-test"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["triage_status"] == "QUEUED"
