"""Tenant isolation middleware for the AI Agent SOC API."""

from __future__ import annotations

import logging
from typing import Callable

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

AUTH_BYPASS_PATHS = frozenset(["/api/v1/health", "/api/v1/readiness", "/docs", "/redoc", "/openapi.json"])


class TenantMiddleware(BaseHTTPMiddleware):
    """
    Extract and validate the X-Tenant-ID header.

    Attaches tenant_id to request.state if not already set by JWT middleware.
    Ensures tenant isolation throughout the request lifecycle.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path in AUTH_BYPASS_PATHS:
            return await call_next(request)

        # Prefer tenant from JWT (set by AuthMiddleware); fall back to header
        if not hasattr(request.state, "tenant_id") or not request.state.tenant_id:
            tenant_id = request.headers.get("X-Tenant-ID", "").strip()
            if not tenant_id:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"detail": "X-Tenant-ID header is required."},
                )
            request.state.tenant_id = tenant_id

        return await call_next(request)
