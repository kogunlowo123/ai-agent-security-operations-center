"""
AI Agent SOC – LiteLLM Router
Configures the multi-provider LLM router with fallback chains,
retry logic, and budget controls.
"""
from __future__ import annotations

import os
from typing import Any

from litellm import Router


def create_router() -> Router:
    """Instantiate and return a configured LiteLLM Router."""
    model_list: list[dict[str, Any]] = [
        # ── Amazon Bedrock – Claude 3.5 Sonnet (primary) ───────────────
        {
            "model_name": "claude-3-5-sonnet",
            "litellm_params": {
                "model": "bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0",
                "aws_region_name": os.environ.get("AWS_REGION", "us-east-1"),
            },
            "model_info": {
                "max_tokens": 8192,
                "input_cost_per_token": 0.000003,
                "output_cost_per_token": 0.000015,
            },
        },
        # ── Amazon Bedrock – Claude 3 Haiku (fast/cheap fallback) ──────
        {
            "model_name": "claude-3-haiku",
            "litellm_params": {
                "model": "bedrock/anthropic.claude-3-haiku-20240307-v1:0",
                "aws_region_name": os.environ.get("AWS_REGION", "us-east-1"),
            },
            "model_info": {
                "max_tokens": 4096,
                "input_cost_per_token": 0.00000025,
                "output_cost_per_token": 0.00000125,
            },
        },
        # ── Vertex AI – Gemini 1.5 Pro (cross-cloud fallback) ──────────
        {
            "model_name": "vertex-gemini-pro",
            "litellm_params": {
                "model": "vertex_ai/gemini-1.5-pro-002",
                "vertex_project": os.environ.get("GCP_PROJECT_ID", ""),
                "vertex_location": os.environ.get("GCP_REGION", "us-central1"),
            },
            "model_info": {
                "max_tokens": 8192,
                "input_cost_per_token": 0.00000125,
                "output_cost_per_token": 0.000005,
            },
        },
        # ── Vertex AI – Gemini 1.5 Flash (cost-optimized fallback) ────
        {
            "model_name": "vertex-gemini-flash",
            "litellm_params": {
                "model": "vertex_ai/gemini-1.5-flash-002",
                "vertex_project": os.environ.get("GCP_PROJECT_ID", ""),
                "vertex_location": os.environ.get("GCP_REGION", "us-central1"),
            },
            "model_info": {
                "max_tokens": 8192,
                "input_cost_per_token": 0.000000075,
                "output_cost_per_token": 0.0000003,
            },
        },
    ]

    return Router(
        model_list=model_list,
        fallbacks=[
            {"claude-3-5-sonnet": ["claude-3-haiku", "vertex-gemini-pro"]},
            {"claude-3-haiku": ["vertex-gemini-flash"]},
        ],
        context_window_fallbacks=[
            {"claude-3-5-sonnet": ["claude-3-haiku"]},
        ],
        num_retries=3,
        retry_after=1,
        allowed_fails=2,
        cooldown_time=60,
        routing_strategy="least-busy",
        set_verbose=False,
    )
