"""Unit tests for the security posture scoring endpoint."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.conftest import make_jwt


@pytest.mark.asyncio
async def test_posture_score_returns_200(client: AsyncClient) -> None:
    """The posture score endpoint should return HTTP 200."""
    token = make_jwt()
    response = await client.get(
        "/api/v1/posture/score",
        headers={"Authorization": f"Bearer {token}", "X-Tenant-ID": "tenant-test"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_posture_score_shape(client: AsyncClient) -> None:
    """The posture score response should have the expected fields."""
    token = make_jwt()
    response = await client.get(
        "/api/v1/posture/score",
        headers={"Authorization": f"Bearer {token}", "X-Tenant-ID": "tenant-test"},
    )
    body = response.json()
    assert "overall_score" in body
    assert "rating" in body
    assert "trend" in body
    assert "component_scores" in body
    assert "timestamp" in body


@pytest.mark.asyncio
async def test_posture_score_in_valid_range(client: AsyncClient) -> None:
    """The overall posture score should be between 0 and 100."""
    token = make_jwt()
    response = await client.get(
        "/api/v1/posture/score",
        headers={"Authorization": f"Bearer {token}", "X-Tenant-ID": "tenant-test"},
    )
    body = response.json()
    assert 0.0 <= body["overall_score"] <= 100.0


@pytest.mark.asyncio
async def test_posture_score_has_six_components(client: AsyncClient) -> None:
    """The posture score should contain scores for all 6 components."""
    token = make_jwt()
    response = await client.get(
        "/api/v1/posture/score",
        headers={"Authorization": f"Bearer {token}", "X-Tenant-ID": "tenant-test"},
    )
    body = response.json()
    components = {c["component"] for c in body["component_scores"]}
    expected = {"identity", "policy", "runtime", "supply_chain", "sdlc", "mesh"}
    assert components == expected


@pytest.mark.asyncio
async def test_component_weights_sum_to_one(client: AsyncClient) -> None:
    """The component weights should sum to approximately 1.0."""
    token = make_jwt()
    response = await client.get(
        "/api/v1/posture/score",
        headers={"Authorization": f"Bearer {token}", "X-Tenant-ID": "tenant-test"},
    )
    body = response.json()
    total_weight = sum(c["weight"] for c in body["component_scores"])
    assert abs(total_weight - 1.0) < 0.001


@pytest.mark.asyncio
async def test_posture_rating_valid(client: AsyncClient) -> None:
    """The posture rating should be one of the valid enumeration values."""
    token = make_jwt()
    response = await client.get(
        "/api/v1/posture/score",
        headers={"Authorization": f"Bearer {token}", "X-Tenant-ID": "tenant-test"},
    )
    body = response.json()
    valid_ratings = {"EXCELLENT", "GOOD", "FAIR", "POOR", "CRITICAL"}
    assert body["rating"] in valid_ratings


@pytest.mark.asyncio
async def test_posture_trend_valid(client: AsyncClient) -> None:
    """The posture trend should be one of the valid enumeration values."""
    token = make_jwt()
    response = await client.get(
        "/api/v1/posture/score",
        headers={"Authorization": f"Bearer {token}", "X-Tenant-ID": "tenant-test"},
    )
    body = response.json()
    valid_trends = {"IMPROVING", "DEGRADING", "STABLE"}
    assert body["trend"] in valid_trends


@pytest.mark.asyncio
async def test_posture_recommendations_present(client: AsyncClient) -> None:
    """The posture score response should include at least one recommendation."""
    token = make_jwt()
    response = await client.get(
        "/api/v1/posture/score",
        headers={"Authorization": f"Bearer {token}", "X-Tenant-ID": "tenant-test"},
    )
    body = response.json()
    assert isinstance(body.get("recommendations"), list)
    assert len(body["recommendations"]) >= 1


@pytest.mark.asyncio
async def test_posture_requires_auth(client: AsyncClient) -> None:
    """The posture endpoint requires an Authorization header."""
    response = await client.get(
        "/api/v1/posture/score",
        headers={"X-Tenant-ID": "tenant-test"},
    )
    assert response.status_code == 401
