"""JWT authentication middleware for the AI Agent SOC API."""

from __future__ import annotations

import logging
from typing import Callable

import jwt
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# Endpoints that bypass authentication
AUTH_BYPASS_PATHS = frozenset(
    [
        "/api/v1/health",
        "/api/v1/readiness",
        "/docs",
        "/redoc",
        "/openapi.json",
    ]
)


class JWTAuthMiddleware(BaseHTTPMiddleware):
    """
    Validate RS256 JWT Bearer tokens on all protected endpoints.

    Extracts tenant_id, principal_id, and scopes from the token payload
    and attaches them to request.state for downstream use.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path in AUTH_BYPASS_PATHS:
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Missing or malformed Authorization header."},
                headers={"WWW-Authenticate": "Bearer"},
            )

        token = auth_header.removeprefix("Bearer ").strip()
        settings = request.app.state.settings

        try:
            payload = jwt.decode(
                token,
                settings.jwt_secret,
                algorithms=[settings.jwt_algorithm],
                audience="ai-agent-soc-api",
                options={"verify_exp": True, "verify_aud": True},
            )
        except jwt.ExpiredSignatureError:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Token has expired."},
                headers={"WWW-Authenticate": "Bearer error=\"invalid_token\""},
            )
        except jwt.InvalidTokenError as exc:
            logger.debug("JWT validation failed: %s", exc)
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Invalid token."},
                headers={"WWW-Authenticate": "Bearer error=\"invalid_token\""},
            )

        request.state.tenant_id = payload.get("tenant_id", "default")
        request.state.principal_id = payload.get("sub", "unknown")
        request.state.scopes = payload.get("scopes", [])

        return await call_next(request)
