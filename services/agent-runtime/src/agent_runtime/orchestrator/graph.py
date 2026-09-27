"""LangGraph orchestration graphs for SOC agents."""

from __future__ import annotations

import logging
import re
from typing import Any, Literal, Optional

import litellm
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from agent_runtime.orchestrator.state import (
    IncidentResponderState,
    SOCAnalystState,
    ThreatHunterState,
)
from agent_runtime.tools.incident_create import IncidentCreateTool
from agent_runtime.tools.mitre_lookup import MitreLookupTool
from agent_runtime.tools.rag_search import RagSearchTool
from agent_runtime.tools.siem_query import SiemQueryTool

logger = logging.getLogger(__name__)

_rag_tool = RagSearchTool()
_siem_tool = SiemQueryTool()
_mitre_tool = MitreLookupTool()
_incident_tool = IncidentCreateTool()

SOC_ANALYST_SYSTEM_PROMPT = """You are a Tier-1 SOC Analyst specializing in AI agent security.
Your role is to:
1. Triage incoming security alerts from AI agent systems
2. Correlate events with the MITRE ATT&CK framework
3. Investigate using SIEM data and threat intelligence
4. Create incidents for confirmed threats
5. Provide a severity score (0-10) in your analysis

Always cite your sources. Never make claims without evidence from retrieved context.
Format your analysis as:
- Severity Score: X/10
- MITRE Techniques: [T1078, ...]
- Analysis: ...
- Verdict: TRUE_POSITIVE | FALSE_POSITIVE | ESCALATED
- Citations: [source1, source2, ...]"""

THREAT_HUNTER_SYSTEM_PROMPT = """You are a Tier-1 Threat Hunter specializing in proactive AI agent security.
Your role is to:
1. Formulate precise SIEM queries based on the hunt hypothesis
2. Analyze SIEM results for indicators of compromise
3. Align findings with MITRE ATT&CK techniques
4. Produce actionable threat hunt reports

Be methodical and evidence-based. Every finding must reference SIEM evidence."""

INCIDENT_RESPONDER_SYSTEM_PROMPT = """You are a Tier-2 Incident Responder.
Your role is to:
1. Manage the incident response lifecycle
2. Select appropriate SOAR playbooks
3. Coordinate remediation steps
4. Ensure proper escalation and communication

Follow the principle of least action: prefer reversible, contained responses."""


# ---------------------------------------------------------------------------
# SOC Analyst graph nodes
# ---------------------------------------------------------------------------


async def enrich_alert(state: dict[str, Any]) -> dict[str, Any]:
    """Normalize and enrich the incoming alert with context."""
    alert = state.get("alert", {})
    source_repo = alert.get("data", {}).get("source_repo", alert.get("source_repo", "unknown"))
    event_type = alert.get("type", "unknown")

    normalized = {
        "id": alert.get("id", "unknown"),
        "type": event_type,
        "source": alert.get("source", ""),
        "time": alert.get("time", ""),
        "source_repo": source_repo,
        "severity": alert.get("data", {}).get("severity", alert.get("severity", "MEDIUM")),
        "principal_id": alert.get("data", {}).get("principal_id", "unknown"),
        "tier": alert.get("data", {}).get("tier", "T1"),
        "payload": alert.get("data", {}).get("payload", {}),
    }

    return {**state, "alert": normalized, "hop_count": 0, "error": None}


async def retrieve_mitre_context(state: dict[str, Any]) -> dict[str, Any]:
    """Retrieve MITRE ATT&CK context for the alert type."""
    alert = state["alert"]
    query = (
        f"MITRE ATT&CK techniques for {alert['type']} "
        f"from {alert['source_repo']} AI agent security"
    )
    try:
        docs = await _rag_tool.search(query, corpus="mitre-attck", top_k=5)
        tactics = _mitre_tool.extract_tactics(docs)
        techniques = await _mitre_tool.map_event_to_techniques(alert["type"])
    except Exception as exc:
        logger.warning("MITRE context retrieval failed: %s", exc)
        docs, tactics, techniques = [], [], []

    return {
        **state,
        "retrieved_context": docs,
        "mitre_tactics": tactics,
        "mitre_techniques": techniques,
        "hop_count": state.get("hop_count", 0) + 1,
    }


async def retrieve_similar_incidents(state: dict[str, Any]) -> dict[str, Any]:
    """Query SIEM for similar historical incidents."""
    alert = state["alert"]
    try:
        query = {
            "query": {
                "bool": {
                    "must": [
                        {"term": {"event_type.keyword": alert["type"]}},
                        {"term": {"source_repo.keyword": alert["source_repo"]}},
                    ],
                    "filter": [{"range": {"@timestamp": {"gte": "now-30d"}}}],
                }
            },
            "size": 5,
            "sort": [{"severity_score": {"order": "desc"}}],
        }
        results = await _siem_tool.query(query)
    except Exception as exc:
        logger.warning("Similar incident retrieval failed: %s", exc)
        results = []

    return {**state, "similar_incidents": results}


async def analyze_threat(state: dict[str, Any]) -> dict[str, Any]:
    """Use LLM to analyze the threat with retrieved context."""
    alert = state["alert"]
    context = state.get("retrieved_context", [])
    similar = state.get("similar_incidents", [])

    context_text = "\n\n".join(
        doc.get("content", "") for doc in context[:3] if isinstance(doc, dict)
    )
    similar_text = "\n".join(
        f"- Incident {i['id']}: {i.get('description', '')[:200]}"
        for i in similar[:3]
        if isinstance(i, dict)
    )

    user_prompt = f"""Alert Details:
- Type: {alert['type']}
- Severity: {alert['severity']}
- Source: {alert['source_repo']}
- Principal: {alert['principal_id']}
- Payload: {str(alert.get('payload', {}))[:500]}

MITRE Techniques: {', '.join(state.get('mitre_techniques', []))}

Retrieved Context:
{context_text[:2000]}

Similar Historical Incidents:
{similar_text[:1000]}

Analyze this alert and provide your assessment."""

    try:
        response = await litellm.acompletion(
            model="bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0",
            messages=[
                {"role": "system", "content": SOC_ANALYST_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=2000,
            temperature=0.1,
        )
        analysis = response.choices[0].message.content
    except Exception as exc:
        logger.error("LLM analysis failed: %s", exc)
        analysis = f"Analysis failed: {exc}. Manual review required."

    severity_score = _extract_severity_score(analysis, alert["severity"])
    return {**state, "analysis": analysis, "severity_score": severity_score}


async def generate_verdict(state: dict[str, Any]) -> dict[str, Any]:
    """Generate the final triage verdict and extract citations."""
    analysis = state.get("analysis", "")
    severity_score = state.get("severity_score", 5.0)
    context = state.get("retrieved_context", [])

    if "FALSE_POSITIVE" in analysis.upper() or severity_score < 2.0:
        verdict = "FALSE_POSITIVE"
    elif severity_score >= 8.0 or "ESCALATED" in analysis.upper():
        verdict = "ESCALATED"
    else:
        verdict = "TRUE_POSITIVE"

    citations = [
        doc.get("metadata", {}).get("source", doc.get("id", f"source-{i}"))
        for i, doc in enumerate(context)
        if isinstance(doc, dict)
    ]

    return {**state, "verdict": verdict, "citations": citations}


async def create_incident_node(state: dict[str, Any]) -> dict[str, Any]:
    """Create an incident record for confirmed threats."""
    if state.get("verdict") not in ("TRUE_POSITIVE", "ESCALATED"):
        return state

    try:
        incident_id = await _incident_tool.create(
            alert=state["alert"],
            analysis=state.get("analysis", ""),
            mitre_techniques=state.get("mitre_techniques", []),
            severity_score=state.get("severity_score", 5.0),
            verdict=state["verdict"],
        )
        return {**state, "incident_id": incident_id}
    except Exception as exc:
        logger.error("Incident creation failed: %s", exc)
        return {**state, "error": str(exc)}


async def immediate_escalate(state: dict[str, Any]) -> dict[str, Any]:
    """Immediately escalate critical threats, bypassing standard triage."""
    try:
        incident_id = await _incident_tool.create_critical(
            alert=state["alert"],
            analysis=state.get("analysis", "AUTO-ESCALATED: Critical severity"),
            severity_score=10.0,
        )
        return {**state, "incident_id": incident_id, "verdict": "ESCALATED"}
    except Exception as exc:
        logger.error("Critical escalation failed: %s", exc)
        return {**state, "error": str(exc)}


def severity_router(
    state: dict[str, Any],
) -> Literal["immediate_escalate", "generate_verdict", "auto_close"]:
    """Route based on severity score after analysis."""
    score = state.get("severity_score", 0.0)
    if score > 8.0:
        return "immediate_escalate"
    elif score >= 5.0:
        return "generate_verdict"
    else:
        return "auto_close"


async def auto_close(state: dict[str, Any]) -> dict[str, Any]:
    """Auto-close low-severity events as false positives."""
    return {**state, "verdict": "FALSE_POSITIVE", "incident_id": None}


def _extract_severity_score(analysis: str, severity_hint: str) -> float:
    """Extract numeric severity score from LLM analysis text."""
    patterns = [
        r"severity score[:\s]+([0-9]+(?:\.[0-9]+)?)\s*/\s*10",
        r"score[:\s]+([0-9]+(?:\.[0-9]+)?)\s*/\s*10",
        r"\b([0-9]+(?:\.[0-9]+)?)\s*/\s*10\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, analysis, re.IGNORECASE)
        if match:
            score = float(match.group(1))
            return min(10.0, max(0.0, score))

    # Fall back to severity hint
    fallbacks = {"CRITICAL": 9.0, "HIGH": 7.0, "MEDIUM": 5.0, "LOW": 3.0, "INFO": 1.0}
    return fallbacks.get(severity_hint.upper(), 5.0)


# ---------------------------------------------------------------------------
# Build SOC Analyst graph
# ---------------------------------------------------------------------------


def build_soc_analyst_graph() -> Any:
    """Construct and compile the SOC Analyst LangGraph workflow."""
    workflow = StateGraph(dict)

    workflow.add_node("enrich_alert", enrich_alert)
    workflow.add_node("retrieve_mitre_context", retrieve_mitre_context)
    workflow.add_node("retrieve_similar_incidents", retrieve_similar_incidents)
    workflow.add_node("analyze_threat", analyze_threat)
    workflow.add_node("generate_verdict", generate_verdict)
    workflow.add_node("create_incident", create_incident_node)
    workflow.add_node("immediate_escalate", immediate_escalate)
    workflow.add_node("auto_close", auto_close)

    workflow.set_entry_point("enrich_alert")
    workflow.add_edge("enrich_alert", "retrieve_mitre_context")
    workflow.add_edge("retrieve_mitre_context", "retrieve_similar_incidents")
    workflow.add_edge("retrieve_similar_incidents", "analyze_threat")
    workflow.add_conditional_edges(
        "analyze_threat",
        severity_router,
        {
            "immediate_escalate": "immediate_escalate",
            "generate_verdict": "generate_verdict",
            "auto_close": "auto_close",
        },
    )
    workflow.add_edge("generate_verdict", "create_incident")
    workflow.add_edge("create_incident", END)
    workflow.add_edge("immediate_escalate", END)
    workflow.add_edge("auto_close", END)

    return workflow.compile(checkpointer=MemorySaver())


# ---------------------------------------------------------------------------
# Threat Hunter graph nodes
# ---------------------------------------------------------------------------


async def formulate_hunt_query(state: dict[str, Any]) -> dict[str, Any]:
    """Formulate an OpenSearch query from the hunt hypothesis."""
    hypothesis = state.get("hunt_hypothesis", "")
    mitre_technique = state.get("mitre_technique")

    prompt = f"""Generate an OpenSearch query DSL to hunt for: {hypothesis}
{"MITRE Technique: " + mitre_technique if mitre_technique else ""}
Return only valid OpenSearch query JSON."""

    try:
        response = await litellm.acompletion(
            model="bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0",
            messages=[
                {"role": "system", "content": THREAT_HUNTER_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            max_tokens=1000,
            temperature=0.0,
        )
        query_str = response.choices[0].message.content
    except Exception as exc:
        logger.error("Hunt query formulation failed: %s", exc)
        query_str = '{"query": {"match_all": {}}}'

    return {**state, "hunt_query": query_str}


async def execute_siem_hunt(state: dict[str, Any]) -> dict[str, Any]:
    """Execute the hunt query against OpenSearch SIEM."""
    import json

    query_str = state.get("hunt_query", "{}")
    try:
        query = json.loads(query_str)
        results = await _siem_tool.query(query, time_range_hours=state.get("time_range_hours", 24))
    except Exception as exc:
        logger.error("SIEM hunt execution failed: %s", exc)
        results = []

    return {**state, "siem_results": results}


async def align_with_mitre(state: dict[str, Any]) -> dict[str, Any]:
    """Map SIEM findings to MITRE ATT&CK techniques."""
    results = state.get("siem_results", [])
    alignment = []

    for result in results[:10]:
        event_type = result.get("event_type", "")
        techniques = await _mitre_tool.map_event_to_techniques(event_type)
        if techniques:
            alignment.append({"event_type": event_type, "techniques": techniques})

    return {**state, "mitre_alignment": alignment}


async def generate_hunt_report(state: dict[str, Any]) -> dict[str, Any]:
    """Generate an AI-powered threat hunt report."""
    results = state.get("siem_results", [])
    alignment = state.get("mitre_alignment", [])
    hypothesis = state.get("hunt_hypothesis", "")

    findings = []
    for i, result in enumerate(results[:5]):
        findings.append(
            {
                "finding_id": f"F-{i+1:03d}",
                "severity": result.get("severity", "MEDIUM"),
                "title": f"Hunt finding: {result.get('event_type', 'unknown')}",
                "description": str(result)[:500],
                "evidence": [result],
                "mitre_techniques": next(
                    (a["techniques"] for a in alignment if a["event_type"] == result.get("event_type")),
                    [],
                ),
            }
        )

    severity = "HIGH" if len(results) > 10 else "MEDIUM" if results else "LOW"

    try:
        response = await litellm.acompletion(
            model="bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0",
            messages=[
                {"role": "system", "content": THREAT_HUNTER_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Hypothesis: {hypothesis}\nFindings: {findings[:3]}\nGenerate hunt report.",
                },
            ],
            max_tokens=2000,
            temperature=0.2,
        )
        report = response.choices[0].message.content
    except Exception as exc:
        report = f"Hunt completed. {len(results)} events analyzed. {len(findings)} findings. Error generating narrative: {exc}"

    return {**state, "findings": findings, "severity": severity, "report": report}


def build_threat_hunter_graph() -> Any:
    """Construct and compile the Threat Hunter LangGraph workflow."""
    workflow = StateGraph(dict)

    workflow.add_node("formulate_hunt_query", formulate_hunt_query)
    workflow.add_node("execute_siem_hunt", execute_siem_hunt)
    workflow.add_node("align_with_mitre", align_with_mitre)
    workflow.add_node("generate_hunt_report", generate_hunt_report)

    workflow.set_entry_point("formulate_hunt_query")
    workflow.add_edge("formulate_hunt_query", "execute_siem_hunt")
    workflow.add_edge("execute_siem_hunt", "align_with_mitre")
    workflow.add_edge("align_with_mitre", "generate_hunt_report")
    workflow.add_edge("generate_hunt_report", END)

    return workflow.compile(checkpointer=MemorySaver())


# Module-level compiled graphs
soc_analyst_graph = build_soc_analyst_graph()
threat_hunter_graph = build_threat_hunter_graph()
