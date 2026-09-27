"""Unit tests for the threat hunt endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock

from tests.conftest import make_jwt

VALID_HUNT_REQUEST = {
    "hypothesis": "AI agents are performing privilege escalation via IAM role chaining",
    "hunt_type": "TECHNIQUE",
    "mitre_technique": "T1078",
    "iocs": [],
    "time_range_hours": 24,
}


@pytest.mark.asyncio
async def test_launch_hunt_returns_202(client: AsyncClient) -> None:
    """Launching a hunt should return HTTP 202 Accepted."""
    token = make_jwt()
    response = await client.post(
        "/api/v1/hunt/launch",
        json=VALID_HUNT_REQUEST,
        headers={"Authorization": f"Bearer {token}", "X-Tenant-ID": "tenant-test"},
    )
    assert response.status_code == 202


@pytest.mark.asyncio
async def test_launch_hunt_returns_hunt_id(client: AsyncClient) -> None:
    """The launch hunt response should include a hunt_id."""
    token = make_jwt()
    response = await client.post(
        "/api/v1/hunt/launch",
        json=VALID_HUNT_REQUEST,
        headers={"Authorization": f"Bearer {token}", "X-Tenant-ID": "tenant-test"},
    )
    body = response.json()
    assert "hunt_id" in body
    assert body["hunt_id"].startswith("HUNT-")


@pytest.mark.asyncio
async def test_launch_hunt_status_is_pending(client: AsyncClient) -> None:
    """Newly launched hunt should have PENDING status."""
    token = make_jwt()
    response = await client.post(
        "/api/v1/hunt/launch",
        json=VALID_HUNT_REQUEST,
        headers={"Authorization": f"Bearer {token}", "X-Tenant-ID": "tenant-test"},
    )
    body = response.json()
    assert body["status"] == "PENDING"


@pytest.mark.asyncio
async def test_launch_hunt_hypothesis_too_short_returns_422(client: AsyncClient) -> None:
    """Hunt hypothesis shorter than 10 characters should fail validation."""
    token = make_jwt()
    response = await client.post(
        "/api/v1/hunt/launch",
        json={**VALID_HUNT_REQUEST, "hypothesis": "short"},
        headers={"Authorization": f"Bearer {token}", "X-Tenant-ID": "tenant-test"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_hunt_not_found_returns_404(client: AsyncClient) -> None:
    """Getting a non-existent hunt should return 404."""
    token = make_jwt()
    response = await client.get(
        "/api/v1/hunt/HUNT-NONEXIST",
        headers={"Authorization": f"Bearer {token}", "X-Tenant-ID": "tenant-test"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_hunt_launch_without_auth_returns_401(client: AsyncClient) -> None:
    """Hunt launch without Authorization header should return 401."""
    response = await client.post(
        "/api/v1/hunt/launch",
        json=VALID_HUNT_REQUEST,
        headers={"X-Tenant-ID": "tenant-test"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_hunt_ids_are_unique(client: AsyncClient) -> None:
    """Each hunt launch should produce a unique hunt_id."""
    token = make_jwt()
    headers = {"Authorization": f"Bearer {token}", "X-Tenant-ID": "tenant-test"}

    r1 = await client.post("/api/v1/hunt/launch", json=VALID_HUNT_REQUEST, headers=headers)
    r2 = await client.post("/api/v1/hunt/launch", json=VALID_HUNT_REQUEST, headers=headers)

    assert r1.status_code == 202
    assert r2.status_code == 202
    assert r1.json()["hunt_id"] != r2.json()["hunt_id"]
