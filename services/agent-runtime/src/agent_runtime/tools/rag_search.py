"""RAG search tool for the SOC agent runtime."""

from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)


class RagSearchTool:
    """
    Tool for querying the RAG Core service.

    Supports semantic and hybrid retrieval over MITRE ATT&CK,
    playbooks, threat intelligence, and historical incidents.
    """

    def __init__(
        self,
        rag_core_url: str = "http://rag-core:8001",
        timeout_seconds: float = 30.0,
    ) -> None:
        self._base_url = rag_core_url.rstrip("/")
        self._timeout = timeout_seconds

    async def search(
        self,
        query: str,
        corpus: str = "mitre-attck",
        top_k: int = 5,
        tenant_id: Optional[str] = None,
        user_roles: Optional[list[str]] = None,
    ) -> list[dict[str, Any]]:
        """
        Perform a hybrid RAG search over the specified corpus.

        Args:
            query: Natural language search query
            corpus: Corpus to search (mitre-attck, playbooks, threat-intel, incidents)
            top_k: Number of top results to return
            tenant_id: Tenant for ACL filtering
            user_roles: User roles for ACL filtering

        Returns:
            List of document dicts with content and metadata
        """
        payload: dict[str, Any] = {
            "query": query,
            "corpus": corpus,
            "top_k": top_k,
        }
        if tenant_id:
            payload["tenant_id"] = tenant_id
        if user_roles:
            payload["user_roles"] = user_roles

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._base_url}/v1/retrieve",
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                return data.get("documents", [])
        except httpx.ConnectError:
            logger.warning(
                "RAG Core service not reachable at %s; returning empty results",
                self._base_url,
            )
            return []
        except httpx.HTTPStatusError as exc:
            logger.error("RAG Core returned error %s: %s", exc.response.status_code, exc)
            return []
        except Exception as exc:
            logger.error("RAG search failed: %s", exc)
            return []

    async def search_mitre(self, event_type: str, technique_hint: Optional[str] = None) -> list[dict[str, Any]]:
        """Convenience method to search the MITRE ATT&CK corpus."""
        query = f"MITRE ATT&CK technique for {event_type}"
        if technique_hint:
            query += f" {technique_hint}"
        return await self.search(query, corpus="mitre-attck", top_k=5)

    async def search_playbooks(self, incident_type: str) -> list[dict[str, Any]]:
        """Search SOC playbooks for a given incident type."""
        return await self.search(
            f"SOC response playbook for {incident_type}",
            corpus="playbooks",
            top_k=3,
        )

    async def search_similar_incidents(
        self, description: str, top_k: int = 5
    ) -> list[dict[str, Any]]:
        """Find historically similar incidents."""
        return await self.search(description, corpus="incidents", top_k=top_k)
