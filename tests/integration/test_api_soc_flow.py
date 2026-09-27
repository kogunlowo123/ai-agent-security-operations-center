"""Integration tests for the full AI Agent SOC API event flow.

These tests require a running API instance and are skipped unless
INTEGRATION_TEST_URL is set in the environment.
"""

from __future__ import annotations

import os
import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient


INTEGRATION_TEST_URL = os.getenv("INTEGRATION_TEST_URL", "")
INTEGRATION_JWT = os.getenv("INTEGRATION_TEST_JWT", "")


@pytest.fixture()
def integration_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {INTEGRATION_JWT}",
        "X-Tenant-ID": "integration-test-tenant",
    }


@pytest.mark.integration
@pytest.mark.skipif(
    not INTEGRATION_TEST_URL,
    reason="INTEGRATION_TEST_URL environment variable not set",
)
@pytest.mark.asyncio
async def test_full_event_ingest_flow(integration_headers: dict) -> None:
    """Test a complete event ingest → response cycle against a live API."""
    async with AsyncClient(base_url=INTEGRATION_TEST_URL, timeout=30.0) as client:
        event = {
            "specversion": "1.0",
            "type": "identity.access.violation",
            "source": "integration-test/v1",
            "id": str(uuid.uuid4()),
            "time": "2024-01-15T10:30:00Z",
            "datacontenttype": "application/json",
            "data": {
                "principal_id": "integration-test-agent",
                "tier": "T1",
                "severity": "HIGH",
                "source_repo": "ai-agent-identity-governance",
                "payload": {"test": True},
            },
        }
        response = await client.post(
            "/api/v1/events/ingest",
            json=event,
            headers=integration_headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert "event_id" in body
        assert body["triage_status"] in ("QUEUED", "ESCALATED")


@pytest.mark.integration
@pytest.mark.skipif(
    not INTEGRATION_TEST_URL,
    reason="INTEGRATION_TEST_URL environment variable not set",
)
@pytest.mark.asyncio
async def test_posture_score_endpoint(integration_headers: dict) -> None:
    """Test the posture score endpoint against a live API."""
    async with AsyncClient(base_url=INTEGRATION_TEST_URL, timeout=30.0) as client:
        response = await client.get(
            "/api/v1/posture/score",
            headers=integration_headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert 0.0 <= body["overall_score"] <= 100.0


@pytest.mark.integration
@pytest.mark.skipif(
    not INTEGRATION_TEST_URL,
    reason="INTEGRATION_TEST_URL environment variable not set",
)
@pytest.mark.asyncio
async def test_hunt_launch_and_status(integration_headers: dict) -> None:
    """Test launching a hunt and checking its status."""
    async with AsyncClient(base_url=INTEGRATION_TEST_URL, timeout=30.0) as client:
        launch_response = await client.post(
            "/api/v1/hunt/launch",
            json={
                "hypothesis": "Integration test hunt for T1078 privilege escalation",
                "hunt_type": "TECHNIQUE",
                "mitre_technique": "T1078",
                "iocs": [],
                "time_range_hours": 1,
            },
            headers=integration_headers,
        )
        assert launch_response.status_code == 202
        hunt_id = launch_response.json()["hunt_id"]

        status_response = await client.get(
            f"/api/v1/hunt/{hunt_id}",
            headers=integration_headers,
        )
        assert status_response.status_code == 200
        assert status_response.json()["hunt_id"] == hunt_id
