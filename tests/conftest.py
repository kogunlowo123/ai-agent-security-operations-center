"""Shared pytest fixtures for the AI Agent SOC test suite."""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime
from typing import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Ensure the API service src is importable
sys.path.insert(
    0,
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "services",
        "api",
        "src",
    ),
)


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers", "integration: tests requiring live infrastructure services"
    )
    config.addinivalue_line("markers", "security: security-focused tests")


@pytest.fixture()
def mock_db_pool():
    """Mock asyncpg connection pool."""
    pool = MagicMock()
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetch = AsyncMock(return_value=[])
    conn.execute = AsyncMock(return_value="INSERT 0 1")
    conn.fetchval = AsyncMock(return_value=1)

    async def acquire_ctx():
        return conn

    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
    pool.close = AsyncMock()
    return pool, conn


@pytest.fixture()
def mock_opensearch():
    """Mock OpenSearch client."""
    client = MagicMock()
    client.search.return_value = {
        "hits": {"hits": [], "total": {"value": 0}},
        "aggregations": {},
    }
    client.index.return_value = {"result": "created", "_id": "test-id"}
    client.info.return_value = {"version": {"number": "2.14.0"}}
    return client


@pytest.fixture()
def mock_sqs():
    """Mock AWS SQS client."""
    client = MagicMock()
    client.send_message.return_value = {
        "MessageId": "test-message-id-12345",
        "MD5OfMessageBody": "abc123",
    }
    return client


@pytest.fixture()
def app(mock_db_pool, mock_opensearch, mock_sqs):
    """FastAPI test application with mocked dependencies."""
    from api.main import create_app

    application = create_app()
    db_pool, _ = mock_db_pool

    application.state.db_pool = db_pool
    application.state.opensearch_client = mock_opensearch
    application.state.sqs_client = mock_sqs

    # Provide minimal settings
    application.state.settings.sqs_base_url = (
        "https://sqs.us-east-1.amazonaws.com/123456789012"
    )
    application.state.settings.jwt_algorithm = "HS256"
    application.state.settings.jwt_secret = "test-secret-for-unit-tests-only"

    return application


@pytest_asyncio.fixture()
async def client(app) -> AsyncIterator[AsyncClient]:
    """Async HTTP test client for the FastAPI application."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as c:
        yield c


def make_jwt(
    tenant_id: str = "tenant-test",
    principal_id: str = "agent-test-001",
    scopes: list[str] | None = None,
    secret: str = "test-secret-for-unit-tests-only",
    algorithm: str = "HS256",
) -> str:
    """Generate a test JWT token."""
    import jwt

    payload = {
        "sub": principal_id,
        "iss": "ai-agent-soc",
        "aud": "ai-agent-soc-api",
        "tenant_id": tenant_id,
        "scopes": scopes or ["events:ingest", "incidents:read", "hunt:launch", "posture:read"],
        "iat": int(datetime.now(UTC).timestamp()),
        "exp": int(datetime.now(UTC).timestamp()) + 3600,
    }
    return jwt.encode(payload, secret, algorithm=algorithm)


VALID_CLOUD_EVENT = {
    "specversion": "1.0",
    "type": "identity.access.violation",
    "source": "ai-agent-identity-governance/v1",
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "time": "2024-01-15T10:30:00Z",
    "datacontenttype": "application/json",
    "data": {
        "principal_id": "agent-test-001",
        "tier": "T1",
        "severity": "HIGH",
        "source_repo": "ai-agent-identity-governance",
        "payload": {"violation_type": "privilege_escalation"},
    },
}

CRITICAL_CLOUD_EVENT = {
    **VALID_CLOUD_EVENT,
    "id": "critical-event-id-001",
    "data": {
        **VALID_CLOUD_EVENT["data"],
        "severity": "CRITICAL",
    },
}
