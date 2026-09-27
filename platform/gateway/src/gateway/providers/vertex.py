"""
AI Agent SOC – Vertex AI Provider
Encapsulates Vertex AI configuration and Workload Identity authentication.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any

import google.auth
import google.auth.transport.requests
from google.oauth2 import service_account

logger = logging.getLogger(__name__)

_VERTEX_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]


@dataclass
class VertexModelConfig:
    """Configuration for a single Vertex AI model."""
    model_id: str
    project: str
    location: str = "us-central1"
    max_output_tokens: int = 8192
    temperature: float = 0.0
    top_p: float = 1.0
    extra_params: dict[str, Any] = field(default_factory=dict)


class VertexProvider:
    """
    Manages Vertex AI credentials and model configuration.
    Uses Google Workload Identity Federation when running in GKE,
    falling back to Application Default Credentials (ADC).
    """

    def __init__(
        self,
        project_id: str | None = None,
        location: str = "us-central1",
        service_account_json: str | None = None,
    ) -> None:
        self._project_id = project_id or os.environ.get("GCP_PROJECT_ID", "")
        self._location = location
        self._service_account_json = service_account_json or os.environ.get(
            "GOOGLE_APPLICATION_CREDENTIALS"
        )
        self._credentials, self._project = self._build_credentials()

    # ------------------------------------------------------------------
    # Credential construction
    # ------------------------------------------------------------------

    def _build_credentials(self) -> tuple[Any, str]:
        """Return (credentials, project_id) using Workload Identity or ADC."""
        if self._service_account_json:
            credentials = service_account.Credentials.from_service_account_file(
                self._service_account_json,
                scopes=_VERTEX_SCOPES,
            )
            project = self._project_id or credentials.project_id
            logger.info("VertexProvider: using service account credentials")
        else:
            # In GKE with Workload Identity, ADC automatically uses the
            # bound Kubernetes service account → Google service account mapping.
            credentials, project = google.auth.default(scopes=_VERTEX_SCOPES)
            if self._project_id:
                project = self._project_id
            logger.info(
                "VertexProvider: using Application Default Credentials (Workload Identity)"
            )

        return credentials, project

    def refresh_credentials(self) -> None:
        """Force-refresh the credentials token."""
        request = google.auth.transport.requests.Request()
        self._credentials.refresh(request)
        logger.debug("VertexProvider: credentials refreshed")

    # ------------------------------------------------------------------
    # Model helpers
    # ------------------------------------------------------------------

    def get_model_config(self, model_name: str) -> VertexModelConfig:
        """Return a VertexModelConfig for the given model name."""
        model_map = {
            "vertex-gemini-pro": "gemini-1.5-pro-002",
            "vertex-gemini-flash": "gemini-1.5-flash-002",
        }
        if model_name not in model_map:
            raise ValueError(
                f"Unknown Vertex model '{model_name}'. "
                f"Available: {list(model_map.keys())}"
            )
        return VertexModelConfig(
            model_id=model_map[model_name],
            project=self._project,
            location=self._location,
        )

    @property
    def credentials(self) -> Any:
        """Expose the underlying Google credentials object."""
        return self._credentials

    @property
    def project_id(self) -> str:
        return self._project
