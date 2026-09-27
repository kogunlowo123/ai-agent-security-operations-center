"""MITRE ATT&CK lookup tool for the SOC agent runtime."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# Static mapping: event type → MITRE ATT&CK technique IDs
EVENT_TECHNIQUE_MAP: dict[str, list[str]] = {
    "identity.access.violation": ["T1078", "T1134"],
    "policy.enforcement.breach": ["T1562", "T1190"],
    "supply_chain.integrity.failure": ["T1195", "T1553"],
    "gateway.abuse.detected": ["T1190", "T1498"],
    "runtime.guardrail.triggered": ["T1059", "T1027"],
    "mesh.anomaly.detected": ["T1021", "T1071"],
    "privacy.violation.detected": ["T1041", "T1567"],
    "sdlc.vulnerability.found": ["T1190", "T1203"],
    "cost.anomaly.detected": ["T1496", "T1530"],
}

# Technique metadata cache (populated from MITRE corpus)
TECHNIQUE_METADATA: dict[str, dict] = {
    "T1078": {"tactic": "Defense Evasion, Persistence, Privilege Escalation, Initial Access", "name": "Valid Accounts"},
    "T1134": {"tactic": "Defense Evasion, Privilege Escalation", "name": "Access Token Manipulation"},
    "T1562": {"tactic": "Defense Evasion", "name": "Impair Defenses"},
    "T1190": {"tactic": "Initial Access", "name": "Exploit Public-Facing Application"},
    "T1195": {"tactic": "Initial Access", "name": "Supply Chain Compromise"},
    "T1553": {"tactic": "Defense Evasion", "name": "Subvert Trust Controls"},
    "T1498": {"tactic": "Impact", "name": "Network Denial of Service"},
    "T1059": {"tactic": "Execution", "name": "Command and Scripting Interpreter"},
    "T1027": {"tactic": "Defense Evasion", "name": "Obfuscated Files or Information"},
    "T1021": {"tactic": "Lateral Movement", "name": "Remote Services"},
    "T1071": {"tactic": "Command and Control", "name": "Application Layer Protocol"},
    "T1041": {"tactic": "Exfiltration", "name": "Exfiltration Over C2 Channel"},
    "T1567": {"tactic": "Exfiltration", "name": "Exfiltration Over Web Service"},
    "T1203": {"tactic": "Execution", "name": "Exploitation for Client Execution"},
    "T1496": {"tactic": "Impact", "name": "Resource Hijacking"},
    "T1530": {"tactic": "Collection", "name": "Data from Cloud Storage"},
}


@dataclass
class MitreLookupResult:
    """Result of a MITRE ATT&CK technique lookup."""

    technique_id: str
    tactic: str
    name: str
    description: str = ""
    mitigations: list[str] = field(default_factory=list)
    url: str = ""

    def __post_init__(self) -> None:
        if not self.url:
            self.url = f"https://attack.mitre.org/techniques/{self.technique_id}/"


class MitreLookupTool:
    """
    Tool for looking up MITRE ATT&CK techniques.

    Provides static mappings from event types to techniques,
    with optional RAG-backed enrichment for detailed metadata.
    """

    def __init__(self, rag_tool=None) -> None:
        self._rag = rag_tool

    async def map_event_to_techniques(self, event_type: str) -> list[str]:
        """Return MITRE technique IDs for a given event type."""
        return EVENT_TECHNIQUE_MAP.get(event_type, [])

    async def lookup(self, technique_id: str) -> Optional[MitreLookupResult]:
        """Return technique metadata for a given ATT&CK technique ID."""
        meta = TECHNIQUE_METADATA.get(technique_id)
        if meta is None:
            logger.warning("Unknown MITRE technique: %s", technique_id)
            return None

        description = ""
        mitigations: list[str] = []

        if self._rag is not None:
            try:
                docs = await self._rag.search(
                    f"MITRE ATT&CK {technique_id} {meta['name']}",
                    corpus="mitre-attck",
                    top_k=3,
                )
                if docs:
                    description = docs[0].get("content", "")[:500]
            except Exception as exc:
                logger.debug("RAG enrichment for %s failed: %s", technique_id, exc)

        return MitreLookupResult(
            technique_id=technique_id,
            tactic=meta["tactic"],
            name=meta["name"],
            description=description,
            mitigations=mitigations,
        )

    def extract_tactics(self, docs: list[dict]) -> list[str]:
        """Extract unique MITRE tactic names from retrieved documents."""
        tactics: set[str] = set()
        for doc in docs:
            metadata = doc.get("metadata", {})
            tactic = metadata.get("mitre_tactic") or doc.get("tactic", "")
            if tactic:
                for t in tactic.split(","):
                    stripped = t.strip()
                    if stripped:
                        tactics.add(stripped)
        return sorted(tactics)

    async def get_mitigations(self, technique_id: str) -> list[str]:
        """Return mitigation descriptions for a technique."""
        if self._rag is None:
            return []
        try:
            docs = await self._rag.search(
                f"MITRE ATT&CK mitigation for {technique_id}",
                corpus="mitre-attck",
                top_k=3,
            )
            return [doc.get("content", "")[:300] for doc in docs if doc.get("content")]
        except Exception as exc:
            logger.debug("Mitigation retrieval for %s failed: %s", technique_id, exc)
            return []
