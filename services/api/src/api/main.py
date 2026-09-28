"""FastAPI application entry point for the AI Agent Security Operations Center."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

import asyncpg
import boto3
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from opensearchpy import OpenSearch
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from pydantic_settings import BaseSettings, SettingsConfigDict

from api.middleware.auth import JWTAuthMiddleware
from api.routes.v1.events import router as events_router
from api.routes.v1.health import router as health_router
from api.routes.v1.hunt import router as hunt_router
from api.routes.v1.incidents import router as incidents_router
from api.routes.v1.posture import router as posture_router

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    app_port: int = 8000
    log_level: str = "INFO"
    secret_key: str = "change-me-in-production"

    # AWS
    aws_region: str = "us-east-1"
    aws_account_id: str = ""
    sqs_base_url: str = ""

    # Database
    database_url: str = "postgresql://soc_user:soc_password@localhost:5432/soc_db"
    database_pool_size: int = 10
    database_max_overflow: int = 20

    # OpenSearch
    opensearch_url: str = "https://localhost:9200"
    opensearch_username: str = "admin"
    opensearch_password: str = "change-me"

    # Auth
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "RS256"
    jwt_access_token_expire_minutes: int = 60

    # OTel
    otel_exporter_otlp_endpoint: str = "http://localhost:4317"
    otel_service_name: str = "ai-agent-soc"

    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:8080"]


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )


def _configure_telemetry(settings: Settings) -> None:
    resource = Resource.create({"service.name": settings.otel_service_name})
    provider = TracerProvider(resource=resource)
    if settings.otel_exporter_otlp_endpoint:
        exporter = OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifecycle: initialize and teardown shared resources."""
    settings: Settings = app.state.settings

    # PostgreSQL connection pool
    try:
        db_pool = await asyncpg.create_pool(
            dsn=settings.database_url,
            min_size=2,
            max_size=settings.database_pool_size,
            command_timeout=30,
        )
        app.state.db_pool = db_pool
        logger.info("PostgreSQL connection pool established")
    except Exception as exc:
        logger.warning("PostgreSQL connection pool failed to initialize: %s", exc)
        app.state.db_pool = None

    # OpenSearch client
    try:
        parsed_url = settings.opensearch_url.replace("https://", "").replace("http://", "")
        host, _, port_str = parsed_url.rpartition(":")
        port = int(port_str) if port_str.isdigit() else 9200
        opensearch = OpenSearch(
            hosts=[{"host": host or parsed_url, "port": port}],
            http_auth=(settings.opensearch_username, settings.opensearch_password),
            use_ssl=settings.opensearch_url.startswith("https"),
            verify_certs=settings.app_env == "production",
            ssl_show_warn=False,
            timeout=30,
        )
        app.state.opensearch_client = opensearch
        logger.info("OpenSearch client initialized")
    except Exception as exc:
        logger.warning("OpenSearch client failed to initialize: %s", exc)
        app.state.opensearch_client = None

    # AWS SQS client
    try:
        sqs_client = boto3.client("sqs", region_name=settings.aws_region)
        app.state.sqs_client = sqs_client
        # Construct SQS base URL from account ID and region
        if not settings.sqs_base_url and settings.aws_account_id:
            app.state.settings.sqs_base_url = (
                f"https://sqs.{settings.aws_region}.amazonaws.com/{settings.aws_account_id}"
            )
        logger.info("AWS SQS client initialized")
    except Exception as exc:
        logger.warning("AWS SQS client failed to initialize: %s", exc)
        app.state.sqs_client = None

    logger.info("AI Agent SOC API started (env=%s)", settings.app_env)
    yield

    # Teardown
    if app.state.db_pool is not None:
        await app.state.db_pool.close()
        logger.info("PostgreSQL connection pool closed")
    logger.info("AI Agent SOC API shutdown complete")


def create_app() -> FastAPI:
    """Construct and configure the FastAPI application."""
    settings = Settings()
    _configure_logging(settings.log_level)
    _configure_telemetry(settings)

    app = FastAPI(
        title="AI Agent Security Operations Center",
        description=(
            "Enterprise-grade SOC platform for AI agent ecosystems. "
            "Aggregates security signals, runs AI-powered threat triage, "
            "manages incidents, and operates proactive threat hunting."
        ),
        version="0.1.0",
        docs_url="/docs" if settings.app_env != "production" else None,
        redoc_url="/redoc" if settings.app_env != "production" else None,
        lifespan=lifespan,
    )

    app.state.settings = settings

    # Middleware — order matters: outermost first
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Tenant-ID", "X-Request-ID"],
    )
    app.add_middleware(JWTAuthMiddleware)

    # OTel auto-instrumentation
    FastAPIInstrumentor.instrument_app(app)

    # Routers
    api_v1_prefix = "/api/v1"
    app.include_router(health_router, prefix=api_v1_prefix)
    app.include_router(events_router, prefix=api_v1_prefix)
    app.include_router(incidents_router, prefix=api_v1_prefix)
    app.include_router(hunt_router, prefix=api_v1_prefix)
    app.include_router(posture_router, prefix=api_v1_prefix)

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    settings = Settings()
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=settings.app_port,
        reload=settings.app_env == "development",
        log_level=settings.log_level.lower(),
    )
