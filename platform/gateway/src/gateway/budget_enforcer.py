"""
AI Agent SOC – Token Budget Enforcer
Enforces per-tenant token usage limits with Redis-backed counters
and burst allowance support.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import redis

logger = logging.getLogger(__name__)

_DEFAULT_WINDOW_SECONDS = 3600          # 1-hour rolling window
_DEFAULT_BURST_MULTIPLIER = 1.5         # Burst allowance above base limit


class BudgetExceededError(Exception):
    """Raised when a tenant's token budget has been exhausted."""

    def __init__(self, tenant_id: str, used: int, limit: int) -> None:
        self.tenant_id = tenant_id
        self.used = used
        self.limit = limit
        super().__init__(
            f"Token budget exceeded for tenant '{tenant_id}': "
            f"used={used}, limit={limit}"
        )


@dataclass
class TenantBudgetConfig:
    """Per-tenant budget configuration."""
    tenant_id: str
    max_tokens_per_hour: int
    burst_multiplier: float = _DEFAULT_BURST_MULTIPLIER
    window_seconds: int = _DEFAULT_WINDOW_SECONDS

    @property
    def burst_limit(self) -> int:
        return int(self.max_tokens_per_hour * self.burst_multiplier)


class TokenBudgetEnforcer:
    """
    Enforces per-tenant token budgets using Redis sliding-window counters.

    Usage:
        enforcer = TokenBudgetEnforcer(redis_client, budgets)
        enforcer.check_and_record(tenant_id, tokens_requested)  # raises if over budget
    """

    def __init__(
        self,
        redis_client: redis.Redis,
        tenant_budgets: dict[str, TenantBudgetConfig],
        default_max_tokens_per_hour: int = 500_000,
    ) -> None:
        self._redis = redis_client
        self._budgets = tenant_budgets
        self._default_max = default_max_tokens_per_hour

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def check_and_record(
        self,
        tenant_id: str,
        tokens_requested: int,
        allow_burst: bool = False,
    ) -> int:
        """
        Check that tenant_id has budget for tokens_requested and record usage.
        Returns the updated total usage for the window.
        Raises BudgetExceededError if the budget (or burst limit) is exceeded.
        """
        config = self._get_config(tenant_id)
        limit = config.burst_limit if allow_burst else config.max_tokens_per_hour
        key = self._redis_key(tenant_id)

        pipeline = self._redis.pipeline(transaction=True)
        pipeline.incrby(key, tokens_requested)
        pipeline.expire(key, config.window_seconds)
        results = pipeline.execute()
        new_total: int = results[0]

        if new_total > limit:
            # Roll back the increment so the counter stays accurate.
            self._redis.decrby(key, tokens_requested)
            raise BudgetExceededError(
                tenant_id=tenant_id,
                used=new_total - tokens_requested,
                limit=limit,
            )

        logger.debug(
            "Budget check passed: tenant=%s tokens=%d total=%d limit=%d",
            tenant_id,
            tokens_requested,
            new_total,
            limit,
        )
        return new_total

    def get_current_usage(self, tenant_id: str) -> int:
        """Return the current token usage for the tenant within the window."""
        key = self._redis_key(tenant_id)
        value = self._redis.get(key)
        return int(value) if value is not None else 0

    def get_remaining_budget(self, tenant_id: str) -> int:
        """Return the remaining token budget for the tenant."""
        config = self._get_config(tenant_id)
        used = self.get_current_usage(tenant_id)
        return max(0, config.max_tokens_per_hour - used)

    def reset_tenant_budget(self, tenant_id: str) -> None:
        """Manually reset a tenant's usage counter (admin use only)."""
        key = self._redis_key(tenant_id)
        self._redis.delete(key)
        logger.warning("Budget counter reset for tenant=%s", tenant_id)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_config(self, tenant_id: str) -> TenantBudgetConfig:
        """Return the budget config for the tenant, using defaults if not found."""
        if tenant_id in self._budgets:
            return self._budgets[tenant_id]
        logger.warning(
            "No budget config found for tenant='%s'; using default limit=%d",
            tenant_id,
            self._default_max,
        )
        return TenantBudgetConfig(
            tenant_id=tenant_id,
            max_tokens_per_hour=self._default_max,
        )

    @staticmethod
    def _redis_key(tenant_id: str) -> str:
        return f"soc:budget:tokens:{tenant_id}"
