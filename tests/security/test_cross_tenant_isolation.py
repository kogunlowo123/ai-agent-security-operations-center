"""Security tests for cross-tenant isolation in the AI Agent SOC API."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.conftest import VALID_CLOUD_EVENT, make_jwt


@pytest.mark.security
@pytest.mark.asyncio
async def test_tenant_a_cannot_access_tenant_b_incidents(
    client: AsyncClient, mock_db_pool
) -> None:
    """
    Incident owned by tenant-b should not be accessible with a tenant-a JWT.

    The endpoint returns 404 (not 403) to avoid confirming incident existence
    to unauthorized callers (information oracle attack prevention).
    """
    _, mock_conn = mock_db_pool
    mock_conn.fetchrow.return_value = None  # DB enforces tenant_id filter

    token = make_jwt(tenant_id="tenant-a")
    response = await client.get(
        "/api/v1/incidents/INC-BELONGS-TO-TENANT-B",
        headers={"Authorization": f"Bearer {token}", "X-Tenant-ID": "tenant-a"},
    )
    assert response.status_code == 404


@pytest.mark.security
@pytest.mark.asyncio
async def test_missing_tenant_header_returns_400(client: AsyncClient) -> None:
    """
    The event ingest endpoint requires an X-Tenant-ID header.

    Without either a JWT (which includes tenant_id) or the X-Tenant-ID header,
    the tenant middleware should reject the request.
    """
    response = await client.post(
        "/api/v1/events/ingest",
        json=VALID_CLOUD_EVENT,
        # No X-Tenant-ID and no Authorization header
    )
    # Should fail with 401 (no auth) or 400 (no tenant)
    assert response.status_code in (400, 401)


@pytest.mark.security
@pytest.mark.asyncio
async def test_expired_jwt_returns_401(client: AsyncClient) -> None:
    """An expired JWT should result in HTTP 401."""
    import jwt as pyjwt
    from datetime import UTC, datetime, timedelta

    # Issue a token that expired 1 hour ago
    payload = {
        "sub": "agent-test",
        "iss": "ai-agent-soc",
        "aud": "ai-agent-soc-api",
        "tenant_id": "tenant-test",
        "scopes": ["events:ingest"],
        "iat": int((datetime.now(UTC) - timedelta(hours=2)).timestamp()),
        "exp": int((datetime.now(UTC) - timedelta(hours=1)).timestamp()),
    }
    expired_token = pyjwt.encode(payload, "test-secret-for-unit-tests-only", algorithm="HS256")

    response = await client.post(
        "/api/v1/events/ingest",
        json=VALID_CLOUD_EVENT,
        headers={"Authorization": f"Bearer {expired_token}", "X-Tenant-ID": "tenant-test"},
    )
    assert response.status_code == 401


@pytest.mark.security
@pytest.mark.asyncio
async def test_malformed_jwt_returns_401(client: AsyncClient) -> None:
    """A malformed JWT should return HTTP 401."""
    response = await client.post(
        "/api/v1/events/ingest",
        json=VALID_CLOUD_EVENT,
        headers={
            "Authorization": "Bearer this-is-not-a-valid-jwt",
            "X-Tenant-ID": "tenant-test",
        },
    )
    assert response.status_code == 401


@pytest.mark.security
@pytest.mark.asyncio
async def test_health_endpoint_accessible_without_auth(client: AsyncClient) -> None:
    """The health endpoint must be accessible without authentication."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200


@pytest.mark.security
@pytest.mark.asyncio
async def test_readiness_endpoint_accessible_without_auth(client: AsyncClient) -> None:
    """The readiness endpoint must be accessible without authentication."""
    response = await client.get("/api/v1/readiness")
    assert response.status_code in (200, 503)  # May be 503 if deps are mocked
