"""Tests verifying PII handling in the AI Agent SOC event pipeline."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.conftest import VALID_CLOUD_EVENT, make_jwt


@pytest.mark.security
@pytest.mark.asyncio
async def test_event_with_email_in_payload_accepted(client: AsyncClient) -> None:
    """Events containing email addresses in payload should still be accepted."""
    token = make_jwt()
    event = {
        **VALID_CLOUD_EVENT,
        "data": {
            **VALID_CLOUD_EVENT["data"],
            "payload": {
                "user_email": "user@example.com",
                "action": "privilege_escalation",
            },
        },
    }
    response = await client.post(
        "/api/v1/events/ingest",
        json=event,
        headers={"Authorization": f"Bearer {token}", "X-Tenant-ID": "tenant-test"},
    )
    assert response.status_code == 200


@pytest.mark.security
@pytest.mark.asyncio
async def test_event_response_does_not_echo_pii(client: AsyncClient) -> None:
    """The event ingest response should not include payload PII data."""
    token = make_jwt()
    event = {
        **VALID_CLOUD_EVENT,
        "data": {
            **VALID_CLOUD_EVENT["data"],
            "payload": {
                "user_email": "secret@private.com",
                "ssn": "123-45-6789",
            },
        },
    }
    response = await client.post(
        "/api/v1/events/ingest",
        json=event,
        headers={"Authorization": f"Bearer {token}", "X-Tenant-ID": "tenant-test"},
    )
    assert response.status_code == 200
    # Response should only contain event_id, triage_status, incident_id, message, span_id
    body = response.json()
    response_text = str(body)
    assert "123-45-6789" not in response_text
    assert "secret@private.com" not in response_text


@pytest.mark.security
@pytest.mark.asyncio
async def test_health_response_contains_no_credentials(client: AsyncClient) -> None:
    """The health endpoint should not expose any credentials or internal secrets."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    body_text = response.text
    assert "password" not in body_text.lower()
    assert "secret" not in body_text.lower()
    assert "token" not in body_text.lower()
    assert "key" not in body_text.lower()


@pytest.mark.security
@pytest.mark.asyncio
async def test_error_response_does_not_leak_stack_trace(client: AsyncClient) -> None:
    """Error responses should not contain stack traces or internal paths."""
    token = make_jwt()
    # Send an invalid event that will fail validation
    response = await client.post(
        "/api/v1/events/ingest",
        json={"invalid": "payload"},
        headers={"Authorization": f"Bearer {token}", "X-Tenant-ID": "tenant-test"},
    )
    assert response.status_code == 422
    body_text = response.text
    # Should not contain Python file paths
    assert "site-packages" not in body_text
    assert "Traceback" not in body_text
