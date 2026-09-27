"""Health and readiness probe endpoints."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    status_code=status.HTTP_200_OK,
    summary="Liveness probe — returns 200 if the process is alive",
)
async def health() -> dict[str, str]:
    """Kubernetes liveness probe endpoint."""
    return {"status": "ok"}


@router.get(
    "/readiness",
    status_code=status.HTTP_200_OK,
    summary="Readiness probe — checks downstream dependency connectivity",
)
async def readiness(request: Request) -> JSONResponse:
    """
    Kubernetes readiness probe.

    Checks:
    - PostgreSQL connectivity
    - OpenSearch connectivity
    """
    checks: dict[str, Any] = {}
    all_ok = True

    # PostgreSQL check
    db = getattr(request.app.state, "db_pool", None)
    if db is not None:
        try:
            async with db.acquire() as conn:
                await conn.fetchval("SELECT 1")
            checks["postgresql"] = "ok"
        except Exception as exc:
            logger.warning("PostgreSQL readiness check failed: %s", exc)
            checks["postgresql"] = f"error: {exc}"
            all_ok = False
    else:
        checks["postgresql"] = "not_configured"

    # OpenSearch check
    opensearch = getattr(request.app.state, "opensearch_client", None)
    if opensearch is not None:
        try:
            info = opensearch.info()
            checks["opensearch"] = info.get("version", {}).get("number", "ok")
        except Exception as exc:
            logger.warning("OpenSearch readiness check failed: %s", exc)
            checks["opensearch"] = f"error: {exc}"
            all_ok = False
    else:
        checks["opensearch"] = "not_configured"

    http_status = status.HTTP_200_OK if all_ok else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(
        status_code=http_status,
        content={
            "status": "ready" if all_ok else "not_ready",
            "checks": checks,
        },
    )
