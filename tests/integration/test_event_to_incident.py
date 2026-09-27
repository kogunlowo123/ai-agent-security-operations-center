"""Integration tests verifying the event → incident creation pipeline."""

from __future__ import annotations

import os
import uuid

import pytest

INTEGRATION_TEST_URL = os.getenv("INTEGRATION_TEST_URL", "")
INTEGRATION_JWT = os.getenv("INTEGRATION_TEST_JWT", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")
OPENSEARCH_URL = os.getenv("OPENSEARCH_URL", "")


@pytest.fixture
def integration_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {INTEGRATION_JWT}",
        "X-Tenant-ID": "integration-test-tenant",
    }


@pytest.mark.integration
@pytest.mark.skipif(
    not all([INTEGRATION_TEST_URL, DATABASE_URL]),
    reason="INTEGRATION_TEST_URL and DATABASE_URL must both be set",
)
@pytest.mark.asyncio
async def test_critical_event_creates_incident_in_db(integration_headers: dict) -> None:
    """A CRITICAL event should result in a row in the incidents table."""
    import asyncpg
    from httpx import AsyncClient

    event_id = str(uuid.uuid4())
    event = {
        "specversion": "1.0",
        "type": "identity.access.violation",
        "source": "integration-test/v1",
        "id": event_id,
        "time": "2024-01-15T10:30:00Z",
        "datacontenttype": "application/json",
        "data": {
            "principal_id": "integration-test-agent",
            "tier": "T1",
            "severity": "CRITICAL",
            "source_repo": "ai-agent-identity-governance",
            "payload": {"test": True},
        },
    }

    async with AsyncClient(base_url=INTEGRATION_TEST_URL, timeout=30.0) as client:
        response = await client.post(
            "/api/v1/events/ingest",
            json=event,
            headers=integration_headers,
        )
        assert response.status_code == 200
        incident_id = response.json().get("incident_id")
        assert incident_id is not None

    # Verify the incident record exists in the database
    conn = await asyncpg.connect(dsn=DATABASE_URL)
    try:
        row = await conn.fetchrow(
            "SELECT id, status FROM incidents WHERE id = $1",
            incident_id,
        )
        assert row is not None
        assert row["status"] == "OPEN"
    finally:
        await conn.close()


@pytest.mark.integration
@pytest.mark.skipif(
    not all([INTEGRATION_TEST_URL, OPENSEARCH_URL]),
    reason="INTEGRATION_TEST_URL and OPENSEARCH_URL must both be set",
)
@pytest.mark.asyncio
async def test_event_indexed_in_opensearch(integration_headers: dict) -> None:
    """Ingested events should be retrievable from OpenSearch."""
    from opensearchpy import OpenSearch
    from httpx import AsyncClient

    event_id = str(uuid.uuid4())
    event = {
        "specversion": "1.0",
        "type": "policy.enforcement.breach",
        "source": "integration-test/v1",
        "id": event_id,
        "time": "2024-01-15T10:35:00Z",
        "datacontenttype": "application/json",
        "data": {
            "principal_id": "integration-test-agent-2",
            "tier": "T1",
            "severity": "MEDIUM",
            "source_repo": "ai-agent-policy-enforcement-runtime",
            "payload": {"test": True},
        },
    }

    async with AsyncClient(base_url=INTEGRATION_TEST_URL, timeout=30.0) as client:
        response = await client.post(
            "/api/v1/events/ingest",
            json=event,
            headers=integration_headers,
        )
        assert response.status_code == 200
        ingested_event_id = response.json()["event_id"]

    # Give OpenSearch a moment to index
    import asyncio
    await asyncio.sleep(2)

    parsed = OPENSEARCH_URL.replace("https://", "").replace("http://", "")
    host, _, port_str = parsed.rpartition(":")
    opensearch = OpenSearch(
        hosts=[{"host": host or parsed, "port": int(port_str) if port_str.isdigit() else 9200}],
        use_ssl=OPENSEARCH_URL.startswith("https"),
        verify_certs=False,
    )

    result = opensearch.get(index="soc-events-*", id=ingested_event_id, ignore=404)
    assert result.get("found") is True
