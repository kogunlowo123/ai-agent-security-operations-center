"""Unit tests for the incident lifecycle management endpoints."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient

from tests.conftest import make_jwt


def _make_incident_row(
    incident_id: str = "INC-TESTABCD",
    severity: str = "HIGH",
    status: str = "OPEN",
    tenant_id: str = "tenant-test",
) -> dict:
    """Return a mock database row representing an incident."""
    now = datetime.now(UTC)
    return {
        "id": incident_id,
        "title": f"Test incident {incident_id}",
        "description": "Test description for unit tests",
        "severity": severity,
        "status": status,
        "tenant_id": tenant_id,
        "principal_id": "agent-test-001",
        "source_event_id": "event-test-001",
        "source_repo": "ai-agent-identity-governance",
        "mitre_techniques": ["T1078"],
        "analysis": "Test analysis",
        "verdict": "TRUE_POSITIVE",
        "citations": ["source-1"],
        "severity_score": 7.5,
        "assignee": None,
        "timeline": [],
        "remediation_steps": [],
        "created_at": now,
        "updated_at": now,
        "resolved_at": None,
        "tags": ["test"],
        "metadata": {},
    }


@pytest.mark.asyncio
async def test_list_incidents_returns_200(client: AsyncClient, mock_db_pool) -> None:
    """List incidents should return HTTP 200."""
    _, mock_conn = mock_db_pool
    mock_conn.fetchrow.return_value = {"cnt": 0}
    mock_conn.fetch.return_value = []

    token = make_jwt()
    response = await client.get(
        "/api/v1/incidents",
        headers={"Authorization": f"Bearer {token}", "X-Tenant-ID": "tenant-test"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_list_incidents_empty_database(client: AsyncClient, mock_db_pool) -> None:
    """Empty database should return empty items list with total=0."""
    _, mock_conn = mock_db_pool
    mock_conn.fetchrow.return_value = {"cnt": 0}
    mock_conn.fetch.return_value = []

    token = make_jwt()
    response = await client.get(
        "/api/v1/incidents",
        headers={"Authorization": f"Bearer {token}", "X-Tenant-ID": "tenant-test"},
    )
    body = response.json()
    assert body["total"] == 0
    assert body["items"] == []
    assert body["has_more"] is False


@pytest.mark.asyncio
async def test_get_incident_not_found_returns_404(client: AsyncClient, mock_db_pool) -> None:
    """Fetching a non-existent incident ID should return 404."""
    _, mock_conn = mock_db_pool
    mock_conn.fetchrow.return_value = None

    token = make_jwt()
    response = await client.get(
        "/api/v1/incidents/INC-NOTFOUND",
        headers={"Authorization": f"Bearer {token}", "X-Tenant-ID": "tenant-test"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_incident_returns_200_when_found(client: AsyncClient, mock_db_pool) -> None:
    """Fetching an existing incident should return 200 with incident data."""
    _, mock_conn = mock_db_pool
    mock_conn.fetchrow.return_value = _make_incident_row()

    token = make_jwt()
    response = await client.get(
        "/api/v1/incidents/INC-TESTABCD",
        headers={"Authorization": f"Bearer {token}", "X-Tenant-ID": "tenant-test"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "INC-TESTABCD"
    assert body["severity"] == "HIGH"


@pytest.mark.asyncio
async def test_update_incident_no_fields_returns_422(client: AsyncClient, mock_db_pool) -> None:
    """PATCH with no update fields should return HTTP 422."""
    token = make_jwt()
    response = await client.patch(
        "/api/v1/incidents/INC-TESTABCD",
        json={},
        headers={"Authorization": f"Bearer {token}", "X-Tenant-ID": "tenant-test"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_incidents_require_auth(client: AsyncClient) -> None:
    """Incident endpoints should require an Authorization header."""
    response = await client.get(
        "/api/v1/incidents",
        headers={"X-Tenant-ID": "tenant-test"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_cross_tenant_isolation(client: AsyncClient, mock_db_pool) -> None:
    """
    Incidents belonging to tenant-b should not be accessible by tenant-a JWT.

    The DB mock returns None for tenant-a+incident-b combination,
    simulating proper tenant isolation at the query level.
    """
    _, mock_conn = mock_db_pool
    # Simulate no matching row when tenant_id doesn't match
    mock_conn.fetchrow.return_value = None

    # Token is for tenant-a but incident belongs to tenant-b
    token = make_jwt(tenant_id="tenant-a")
    response = await client.get(
        "/api/v1/incidents/INC-TENANTB",
        headers={"Authorization": f"Bearer {token}", "X-Tenant-ID": "tenant-a"},
    )
    # Should return 404 (not 403) to avoid revealing existence
    assert response.status_code == 404
