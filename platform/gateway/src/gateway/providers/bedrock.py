"""
AI Agent SOC – Amazon Bedrock Provider
Encapsulates Bedrock-specific configuration and authentication via IRSA.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any

import boto3
from botocore.config import Config as BotocoreConfig

logger = logging.getLogger(__name__)


@dataclass
class BedrockModelConfig:
    """Configuration for a single Bedrock model."""
    model_id: str
    region: str = "us-east-1"
    max_tokens: int = 8192
    temperature: float = 0.0
    top_p: float = 1.0
    anthropic_version: str = "bedrock-2023-05-31"
    extra_params: dict[str, Any] = field(default_factory=dict)


# Default model configurations
BEDROCK_MODELS: dict[str, BedrockModelConfig] = {
    "claude-3-5-sonnet": BedrockModelConfig(
        model_id="anthropic.claude-3-5-sonnet-20241022-v2:0",
        max_tokens=8192,
        temperature=0.0,
    ),
    "claude-3-haiku": BedrockModelConfig(
        model_id="anthropic.claude-3-haiku-20240307-v1:0",
        max_tokens=4096,
        temperature=0.0,
    ),
}


class BedrockProvider:
    """
    Manages Amazon Bedrock client creation and request signing.
    Authenticates via IRSA (IAM Roles for Service Accounts) when running
    in Kubernetes, or via standard boto3 credential chain otherwise.
    """

    def __init__(
        self,
        region: str = "us-east-1",
        role_arn: str | None = None,
        session_name: str = "soc-gateway-bedrock",
    ) -> None:
        self._region = region
        self._role_arn = role_arn or os.environ.get("BEDROCK_ROLE_ARN")
        self._session_name = session_name
        self._client = self._build_client()

    # ------------------------------------------------------------------
    # Client construction
    # ------------------------------------------------------------------

    def _build_client(self) -> Any:
        """Return an authenticated Bedrock runtime client."""
        botocore_config = BotocoreConfig(
            region_name=self._region,
            retries={"max_attempts": 3, "mode": "adaptive"},
            connect_timeout=10,
            read_timeout=60,
        )

        session = self._assume_role_session() if self._role_arn else boto3.Session()

        client = session.client(
            service_name="bedrock-runtime",
            config=botocore_config,
        )
        logger.info(
            "BedrockProvider initialized: region=%s role=%s",
            self._region,
            self._role_arn or "default-credentials",
        )
        return client

    def _assume_role_session(self) -> boto3.Session:
        """Assume the configured IAM role and return a scoped boto3 session."""
        sts_client = boto3.client("sts", region_name=self._region)
        response = sts_client.assume_role(
            RoleArn=self._role_arn,
            RoleSessionName=self._session_name,
            DurationSeconds=3600,
        )
        credentials = response["Credentials"]
        return boto3.Session(
            aws_access_key_id=credentials["AccessKeyId"],
            aws_secret_access_key=credentials["SecretAccessKey"],
            aws_session_token=credentials["SessionToken"],
        )

    # ------------------------------------------------------------------
    # Model helpers
    # ------------------------------------------------------------------

    @staticmethod
    def get_model_config(model_name: str) -> BedrockModelConfig:
        """Return the configuration for the named model."""
        if model_name not in BEDROCK_MODELS:
            raise ValueError(
                f"Unknown Bedrock model '{model_name}'. "
                f"Available: {list(BEDROCK_MODELS.keys())}"
            )
        return BEDROCK_MODELS[model_name]

    def list_available_models(self) -> list[str]:
        """Return the list of configured Bedrock model names."""
        return list(BEDROCK_MODELS.keys())

    @property
    def client(self) -> Any:
        """Expose the underlying boto3 Bedrock runtime client."""
        return self._client
