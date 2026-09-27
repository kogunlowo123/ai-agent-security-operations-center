"""SIEM query tool for the SOC agent runtime."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any, Optional

logger = logging.getLogger(__name__)


class SiemQueryTool:
    """
    Tool for querying the OpenSearch SIEM data store.

    Executes OpenSearch DSL queries against the soc-events-* index pattern.
    """

    def __init__(self, opensearch_client=None) -> None:
        self._client = opensearch_client

    async def query(
        self,
        query: dict[str, Any],
        time_range_hours: int = 24,
        index_pattern: str = "soc-events-*",
        size: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Execute an OpenSearch DSL query and return matching documents.

        Args:
            query: OpenSearch query DSL dictionary
            time_range_hours: Look-back window in hours
            index_pattern: Index pattern to search
            size: Maximum number of results

        Returns:
            List of matching event documents
        """
        if self._client is None:
            logger.warning("OpenSearch client not available; returning empty results")
            return []

        # Ensure time range filter is applied
        enriched_query = self._add_time_range(query, time_range_hours)
        enriched_query.setdefault("size", min(size, 1000))

        try:
            response = self._client.search(
                index=index_pattern,
                body=enriched_query,
            )
            hits = response.get("hits", {}).get("hits", [])
            return [
                {**hit.get("_source", {}), "_id": hit.get("_id"), "_score": hit.get("_score")}
                for hit in hits
            ]
        except Exception as exc:
            logger.error("SIEM query failed: %s", exc)
            return []

    def _add_time_range(
        self, query: dict[str, Any], time_range_hours: int
    ) -> dict[str, Any]:
        """Inject a time range filter into an existing query."""
        start = datetime.now(UTC) - timedelta(hours=time_range_hours)
        time_filter = {"range": {"@timestamp": {"gte": start.isoformat()}}}

        import copy
        q = copy.deepcopy(query)

        existing = q.get("query", {})
        if "bool" in existing:
            filters = existing["bool"].setdefault("filter", [])
            if isinstance(filters, list):
                filters.append(time_filter)
            else:
                existing["bool"]["filter"] = [filters, time_filter]
        else:
            q["query"] = {
                "bool": {
                    "must": [existing] if existing else [],
                    "filter": [time_filter],
                }
            }

        return q

    async def aggregate(
        self,
        aggregation: dict[str, Any],
        time_range_hours: int = 24,
    ) -> dict[str, Any]:
        """Execute an aggregation query against the SIEM."""
        if self._client is None:
            return {}

        query = {
            "size": 0,
            "query": {
                "range": {
                    "@timestamp": {
                        "gte": (datetime.now(UTC) - timedelta(hours=time_range_hours)).isoformat()
                    }
                }
            },
            "aggs": aggregation,
        }

        try:
            response = self._client.search(index="soc-events-*", body=query)
            return response.get("aggregations", {})
        except Exception as exc:
            logger.error("SIEM aggregation failed: %s", exc)
            return {}

    async def search_by_principal(
        self, principal_id: str, time_range_hours: int = 24, size: int = 50
    ) -> list[dict[str, Any]]:
        """Retrieve all events for a specific principal."""
        return await self.query(
            query={"query": {"term": {"principal_id.keyword": principal_id}}},
            time_range_hours=time_range_hours,
            size=size,
        )
