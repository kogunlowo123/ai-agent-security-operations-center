"""OpenTelemetry tracing middleware for the AI Agent SOC API."""

from __future__ import annotations

import logging
from typing import Callable

from fastapi import Request, Response
from opentelemetry import trace
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)
propagator = TraceContextTextMapPropagator()


class TracingMiddleware(BaseHTTPMiddleware):
    """
    Inject and propagate OpenTelemetry trace context.

    Extracts W3C Trace Context from incoming headers,
    enriches spans with tenant and route attributes.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        context = propagator.extract(dict(request.headers))

        with tracer.start_as_current_span(
            f"{request.method} {request.url.path}",
            context=context,
            kind=trace.SpanKind.SERVER,
        ) as span:
            span.set_attribute("http.method", request.method)
            span.set_attribute("http.url", str(request.url))
            span.set_attribute("http.scheme", request.url.scheme)
            span.set_attribute("net.host.name", request.url.hostname or "")

            tenant_id = getattr(request.state, "tenant_id", None)
            if tenant_id:
                span.set_attribute("tenant.id", tenant_id)

            principal_id = getattr(request.state, "principal_id", None)
            if principal_id:
                span.set_attribute("principal.id", principal_id)

            response = await call_next(request)
            span.set_attribute("http.status_code", response.status_code)
            return response
