# Threat Hunt Playbook

**Version:** 1.0  
**Owner:** SOC Platform Team  
**Last Updated:** 2024-01-20  
**Applies To:** All proactive threat hunting activities using the AI Agent SOC platform

---

## Overview

Threat hunting is a proactive, hypothesis-driven process for finding evidence of threats that automated detections have not surfaced. This playbook covers the full threat hunt lifecycle: forming a hypothesis, executing SIEM queries, analysing results, and producing a report.

The SOC platform provides a dedicated threat hunt API at `/api/v1/hunt/`.

---

## Hunt Lifecycle

```
┌──────────────────┐
│ 1. Hypothesis    │  Define what threat you're looking for
│    Formation     │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ 2. Hunt Launch   │  Submit hunt to the SOC platform
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ 3. SIEM Query    │  AI agent generates and executes OpenSearch queries
│    Execution     │  against event corpus
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ 4. Analysis      │  Analyst reviews agent-generated findings
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ 5. Report &      │  Document findings; escalate or close
│    Escalation    │
└──────────────────┘
```

---

## Phase 1: Hypothesis Formation

A good hunt hypothesis follows the format:

> "I believe [threat actor / technique] is [performing action] by [observable evidence] because [threat intelligence / anomaly]."

### Hypothesis Triggers

Hunts are initiated when any of the following are observed:

| Trigger | Example |
|---------|---------|
| New MITRE ATT&CK technique published relevant to AI agents | T1650 published covering LLM prompt injection |
| Threat intel report implicating a technique against ML systems | Report of T1602 targeting ML model stores |
| Anomaly in security posture score | Posture dropped from 87 → 71 over 48h |
| Pattern observed in low-severity events not yet triggering incidents | Multiple T1078.004 events across different tenants |
| Post-incident follow-up hunt | After INC-ABC123: hunt for lateral movement by same actor |

### Hunt Types

| Type | `hunt_type` value | Description |
|------|-------------------|-------------|
| Technique-based | `TECHNIQUE` | Hunt for a specific MITRE ATT&CK technique |
| IOC-based | `IOC` | Hunt for specific indicators (IPs, hashes, domains) |
| Anomaly-based | `ANOMALY` | Hunt for behavioural anomalies in agent telemetry |
| Incident follow-up | `INCIDENT` | Deep-dive hunt connected to an existing incident |

---

## Phase 2: Hunt Launch

### 2.1 Via API

```bash
# Launch a technique-based hunt
curl -X POST https://soc.internal/api/v1/hunt/launch \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Tenant-ID: $TENANT" \
  -H "Content-Type: application/json" \
  -d '{
    "hypothesis": "AI agents are performing privilege escalation via IAM role chaining after initial credential compromise",
    "hunt_type": "TECHNIQUE",
    "mitre_technique": "T1078.004",
    "iocs": [],
    "time_range_hours": 168,
    "priority_principals": []
  }'
```

**Response:** HTTP 202 with `hunt_id` (format: `HUNT-XXXXXXXXXXXXXXXX`)

```json
{
  "hunt_id": "HUNT-A1B2C3D4E5F6",
  "status": "PENDING",
  "estimated_duration_seconds": 120,
  "created_at": "2024-01-20T14:30:00Z"
}
```

### 2.2 Hunt Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `hypothesis` | Yes | Human-readable hypothesis (10–2000 characters) |
| `hunt_type` | Yes | `TECHNIQUE`, `IOC`, `ANOMALY`, or `INCIDENT` |
| `mitre_technique` | If TECHNIQUE | ATT&CK technique ID (e.g., `T1078.004`) |
| `iocs` | If IOC | List of `{type, value}` objects |
| `time_range_hours` | No | Look-back window; default 168h (7 days) |
| `priority_principals` | No | Subset of agent IDs to focus on |

### 2.3 Polling Hunt Status

```bash
# Poll until status is COMPLETED or FAILED
while true; do
  STATUS=$(curl -s -H "Authorization: Bearer $TOKEN" \
    https://soc.internal/api/v1/hunt/$HUNT_ID | jq -r .status)
  echo "Status: $STATUS"
  [ "$STATUS" = "COMPLETED" ] || [ "$STATUS" = "FAILED" ] && break
  sleep 10
done
```

---

## Phase 3: SIEM Query Execution

The SOC agent automatically generates OpenSearch DSL queries based on the hypothesis and executes them against the event corpus. The analyst does not need to write raw queries.

### 3.1 What the Agent Does

1. **Technique mapping**: Retrieves MITRE ATT&CK technique details from the RAG corpus.
2. **Query generation**: Generates OpenSearch DSL queries targeting event fields most likely to surface the technique.
3. **Query execution**: Runs queries against the `soc-events-*` indices.
4. **Aggregation**: Groups results by `principal_id`, `source_repo`, and time buckets.

### 3.2 Manual Query Override

For advanced analysts who want to execute custom queries:

```bash
# Execute a custom OpenSearch query as part of the hunt
curl -X POST https://soc.internal/api/v1/hunt/$HUNT_ID/query \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "query": {
      "bool": {
        "must": [
          {"term": {"data.severity": "HIGH"}},
          {"wildcard": {"data.payload.action": "*AssumeRole*"}},
          {"range": {"time": {"gte": "now-7d"}}}
        ]
      }
    }
  }'
```

---

## Phase 4: Analysis

### 4.1 Retrieve Hunt Results

```bash
curl -H "Authorization: Bearer $TOKEN" \
  https://soc.internal/api/v1/hunt/$HUNT_ID/results | jq .
```

The results contain:
- `findings`: List of suspicious events with confidence scores
- `affected_principals`: List of agent IDs with finding counts
- `mitre_techniques_confirmed`: Techniques with evidence above the confidence threshold
- `timeline`: Chronological sequence of suspicious events
- `agent_analysis`: Natural language summary from the SOC agent

### 4.2 Analyst Review Criteria

For each finding, the analyst should assess:

1. **Confidence score**: Is the agent's confidence justified by the evidence?
2. **False positive check**: Is there a legitimate explanation (authorized maintenance, known scanner)?
3. **Blast radius**: If this is a True Positive, how many principals/systems are affected?
4. **Novelty**: Does this match known attack patterns, or does it represent a new technique variant?

### 4.3 Decision Outcomes

| Finding | Action |
|---------|--------|
| Confirmed True Positive | Create incident(s) via POST `/api/v1/incidents`; link to hunt |
| Likely True Positive (confidence 0.6–0.85) | Create incident with `verdict: NEEDS_REVIEW`; assign senior analyst |
| False Positive | Document rationale; consider creating a suppression rule |
| Inconclusive | Mark hunt as `ESCALATED`; widen time range or consult threat intel |

---

## Phase 5: Report & Escalation

### 5.1 Hunt Report Structure

Every completed hunt must produce a report stored in the SOC platform:

```bash
curl -X POST https://soc.internal/api/v1/hunt/$HUNT_ID/report \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "executive_summary": "Hunt for T1078.004 over the past 7 days identified 3 suspicious IAM role assumption chains...",
    "findings_summary": "3 TRUE_POSITIVE findings involving agents prod-042, prod-108, and staging-017",
    "affected_systems": ["ai-agent-identity-governance", "ai-agent-policy-enforcement"],
    "incidents_created": ["INC-XY001", "INC-XY002"],
    "false_positives": 2,
    "recommendations": [
      "Implement MFA on all agent IAM roles",
      "Add detection rule for >2 AssumeRole calls within 60 seconds"
    ],
    "hunt_outcome": "TRUE_POSITIVE"
  }'
```

### 5.2 Escalation Criteria

Escalate the hunt immediately to the SOC Lead if:
- More than 3 principals are affected
- The technique spans multiple source repositories (cross-system attack)
- There is evidence of data exfiltration
- The incident SLA is at risk

### 5.3 Post-Hunt Actions

- [ ] Findings documented in hunt report
- [ ] Related incidents created and linked
- [ ] New detection rules proposed (if applicable)
- [ ] Hunt status set to `COMPLETED` or `ESCALATED`
- [ ] MITRE ATT&CK coverage matrix updated
- [ ] Posture score refreshed

---

## Pre-Built Hunt Templates

The following hypothesis templates are available for common AI agent threat scenarios:

### Template: IAM Role Chaining (T1078.004)
```
AI agents in the [SOURCE_REPO] repository are performing privilege escalation via 
IAM role chaining, obtaining elevated permissions not granted in their service 
principal definition, as evidenced by AssumeRole API calls creating chains 
longer than 2 hops.
```

### Template: Model Supply Chain Tampering (T1195.002)
```
A threat actor has tampered with a machine learning model artifact in the 
[MODEL_STORE] repository, injecting adversarial weights or backdoors that 
cause downstream AI agents to exhibit manipulated behaviour on specific trigger inputs.
```

### Template: Prompt Injection via User Input (T1059.007)
```
External users are injecting malicious instructions into AI agent prompts via 
the [INTERFACE] interface, causing agents to perform actions outside their 
authorised scope, including data retrieval and API calls to unauthorized endpoints.
```

### Template: Credential Theft from Agent Environment (T1552)
```
An attacker has compromised the runtime environment of an AI agent and is 
extracting credentials (API keys, AWS credentials, database passwords) from 
environment variables, container metadata endpoints, or secret stores.
```
