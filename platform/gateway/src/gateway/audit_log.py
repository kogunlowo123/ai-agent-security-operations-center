"""
AI Agent SOC – Gateway Audit Logger
Asynchronously logs every LLM invocation to OpenSearch.
Fire-and-forget with background retry on transient failures.
"""
from __future__ import annotations

import asyncio
import datetime
import logging
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_RETRY_BACKOFF_BASE = 1.5   # seconds; exponential: 1.5, 2.25, 3.375


@dataclass
class InvocationRecord:
    """Canonical schema for a single LLM invocation audit record."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.utcnow().isoformat() + "Z"
    )
    model: str = ""
    provider: str = ""
    tenant_id: str = ""
    agent_id: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: int = 0
    status: str = "success"           # success | error | rate_limited
    error_message: Optional[str] = None
    request_id: Optional[str] = None
    trace_id: Optional[str] = None

    def to_opensearch_doc(self) -> dict[str, Any]:
        doc = asdict(self)
        doc["@timestamp"] = doc.pop("timestamp")
        return doc


class AuditLogger:
    """
    Asynchronous, fire-and-forget audit logger that writes invocation
    records to an OpenSearch index.

    Every call to `log()` schedules a background task; the caller is
    not blocked and does not need to await the result.
    """

    def __init__(
        self,
        opensearch_url: str,
        index_prefix: str = "soc-gateway-audit",
        username: str = "",
        password: str = "",
        timeout_seconds: int = 10,
    ) -> None:
        self._opensearch_url = opensearch_url.rstrip("/")
        self._index_prefix = index_prefix
        self._auth = (username, password) if username else None
        self._timeout = timeout_seconds

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def log(self, record: InvocationRecord) -> None:
        """Schedule a fire-and-forget audit log write."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(self._write_with_retry(record))
            else:
                loop.run_until_complete(self._write_with_retry(record))
        except RuntimeError:
            # No event loop — write synchronously as last resort.
            asyncio.run(self._write_with_retry(record))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _index_name(self) -> str:
        today = datetime.datetime.utcnow().strftime("%Y.%m.%d")
        return f"{self._index_prefix}-{today}"

    async def _write_with_retry(self, record: InvocationRecord) -> None:
        """Attempt to write record to OpenSearch with exponential backoff."""
        url = f"{self._opensearch_url}/{self._index_name()}/_doc/{record.id}"
        doc = record.to_opensearch_doc()
        delay = _RETRY_BACKOFF_BASE

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for attempt in range(1, _MAX_RETRIES + 1):
                try:
                    response = await client.put(
                        url,
                        json=doc,
                        auth=self._auth,
                        headers={"Content-Type": "application/json"},
                    )
                    if response.status_code in (200, 201):
                        logger.debug(
                            "Audit log written: id=%s tenant=%s model=%s",
                            record.id,
                            record.tenant_id,
                            record.model,
                        )
                        return
                    logger.warning(
                        "Audit log write failed (attempt %d/%d): status=%d body=%s",
                        attempt,
                        _MAX_RETRIES,
                        response.status_code,
                        response.text[:200],
                    )
                except (httpx.ConnectError, httpx.TimeoutException) as exc:
                    logger.warning(
                        "Audit log network error (attempt %d/%d): %s",
                        attempt,
                        _MAX_RETRIES,
                        exc,
                    )

                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(delay)
                    delay *= _RETRY_BACKOFF_BASE

        logger.error(
            "Audit log permanently failed after %d attempts: id=%s tenant=%s",
            _MAX_RETRIES,
            record.id,
            record.tenant_id,
        )
