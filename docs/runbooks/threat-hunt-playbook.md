# Threat Hunt Playbook

**Version:** 1.3  
**Owner:** Threat Intelligence & Hunting Team  
**Last Updated:** 2024-12-01  
**Review Cadence:** Quarterly  

---

## Overview

This playbook defines the structured methodology for conducting proactive threat hunts using the AI Agent SOC platform. Threat hunting is a proactive, iterative process that searches for threats that have evaded existing automated detections.

**When to Hunt:**
- After a CRITICAL or HIGH incident in the same tenant or sector
- After a new MITRE ATT&CK technique is added relevant to our threat profile
- When threat intelligence indicates a specific adversary is targeting our sector
- On a scheduled cadence (weekly for high-risk asset groups, monthly for standard)
- When posture score degrades below GOOD rating

---

## Phase 1: Hypothesis Formation

A hunt hypothesis is a falsifiable statement about adversary behaviour in the environment.

**Good hypothesis format:**
> "Threat actor [X] is using technique [ATT&CK ID] to achieve [objective] by [mechanism]."

**Example hypotheses:**
- "An attacker is performing credential dumping (T1003) from LSASS on domain controllers to enable lateral movement."
- "A supply chain compromise (T1195) has introduced a malicious npm package that is beaconing to attacker infrastructure."
- "A compromised insider (T1078) is staging sensitive data (T1074) in staging buckets for exfiltration."

**Hypothesis sources:**
1. **AI Agent**: use the threat hunt agent to generate hypotheses based on current posture signals and threat intel
2. **Threat Intel**: ISAC bulletins, vendor threat reports, recent CVE disclosures
3. **ATT&CK Threat Groups**: review techniques used by threat groups targeting financial services (see MITRE Navigator layer `threat-intel/navigator-layers/fs-sector.json`)
4. **Recent Incidents**: what did the last PIR recommend hunting for?

### 1.1 Create Hunt via API

```bash
POST /api/v1/threat-hunts
{
  "hypothesis": "Pass-the-Hash lateral movement from compromised finance workstations to domain controllers using harvested NTLM hashes",
  "mitre_technique": "T1550.002",
  "threat_group": "APT40",
  "scope": {
    "timerange_hours": 168,
    "asset_groups": ["domain-controllers", "finance-workstations"],
    "cloud_providers": ["aws", "azure"]
  },
  "priority": "HIGH"
}
```

---

## Phase 2: SIEM Query Development

### 2.1 Query Design Principles

- Always scope queries by `tenant_id` first to prevent cross-tenant data access
- Use time-boxed queries — open-ended queries across all time are expensive and may miss recent activity
- Start broad, then narrow: identify the data shape before applying strict filters
- Preserve raw query text in hunt notes for reproducibility

### 2.2 Query Templates by Technique Category

**T1550.002 — Pass-the-Hash:**
```json
GET soc-events-*/_search
{
  "query": {
    "bool": {
      "must": [
        {"term": {"tenant_id": "<TENANT>"}},
        {"term": {"event_type": "auth.login.success"}},
        {"term": {"data.auth_method": "ntlm"}},
        {"range": {"time": {"gte": "now-7d"}}}
      ],
      "filter": [
        {"terms": {"data.destination_host": ["DC-PROD-01", "DC-PROD-02"]}}
      ]
    }
  },
  "aggs": {
    "by_source_host": {"terms": {"field": "data.source_host.keyword", "size": 50}}
  }
}
```

**T1003.001 — LSASS Memory Dump:**
```json
GET soc-events-*/_search
{
  "query": {
    "bool": {
      "must": [
        {"term": {"tenant_id": "<TENANT>"}},
        {"term": {"event_type": "process.create"}},
        {"term": {"data.target_process": "lsass.exe"}},
        {"range": {"time": {"gte": "now-7d"}}}
      ]
    }
  }
}
```

**T1041 — Exfiltration over C2 Channel (large outbound transfers):**
```json
GET soc-events-*/_search
{
  "query": {
    "bool": {
      "must": [
        {"term": {"tenant_id": "<TENANT>"}},
        {"term": {"event_type": "network.anomaly.detected"}},
        {"range": {"data.bytes_transferred": {"gte": 104857600}}},
        {"range": {"time": {"gte": "now-7d"}}}
      ]
    }
  },
  "sort": [{"data.bytes_transferred": "desc"}]
}
```

### 2.3 Launch Hunt Query via CLI

```bash
soc-cli hunt query \
  --hunt-id <HUNT-ID> \
  --query-file queries/hunt-T1550.002.json \
  --save-results
```

---

## Phase 3: Data Collection and Analysis

### 3.1 Collect Evidence

For each query result set:

1. **Review top 20 results** manually — look for patterns the automated ranking may have missed
2. **Entity enrichment**: use the platform's enrichment API to get threat intel context for any external IPs, domains, or file hashes
3. **Timeline reconstruction**: order events chronologically to understand the attack progression
4. **Lateral movement mapping**: visualise host-to-host connections using the graph view

```bash
# Enrich an IP address against threat intel
soc-cli intel enrich --type ip --value 203.0.113.5

# Enrich a file hash
soc-cli intel enrich --type sha256 --value <HASH>
```

### 3.2 True Positive Confirmation Criteria

A finding is a **confirmed True Positive** when:

- [ ] The anomalous behaviour matches the ATT&CK technique's known implementation
- [ ] At least two independent data sources confirm the activity (e.g., EDR + network logs)
- [ ] The activity cannot be explained by an authorised change record or scheduled task
- [ ] The confidence score from the AI triage agent is ≥ 0.80

A finding is a **False Positive** when:

- [ ] The activity matches an authorised change record (check ServiceNow)
- [ ] The source is a known scanner or automation account (check the allowlist)
- [ ] The signature matches but the context (time, user, system) is consistent with normal operations

### 3.3 Pivot Investigation

When a True Positive is confirmed:

1. **Pivot by entity**: search for all activity by the compromised account/host in the last 30 days
2. **Pivot by IOC**: search for the identified IP/domain/hash across all tenants (platform-wide hunt, requires elevated privileges)
3. **Temporal expansion**: extend the time window backwards to find the initial access vector

---

## Phase 4: Reporting

### 4.1 Hunt Report Structure

Every completed hunt must produce a hunt report following this structure:

1. **Executive Summary** (3–5 sentences): What was hunted, what was found, recommended action
2. **Hypothesis**: The original hunt hypothesis and whether it was validated
3. **Methodology**: Queries run, data sources used, time period covered
4. **Findings**: 
   - Confirmed True Positives (with ATT&CK mapping)
   - Notable False Positives (for false positive registry update)
   - Negative findings (evidence the hypothesis was NOT validated)
5. **MITRE ATT&CK Coverage**: Heatmap delta — which techniques now have better coverage
6. **Recommendations**: 
   - New detection rules to create
   - Posture improvements
   - Follow-on hunts
7. **IOC List**: IPs, domains, file hashes, registry keys found during the hunt

### 4.2 Submit Hunt Report

```bash
# Update hunt status to COMPLETED and attach report
PATCH /api/v1/threat-hunts/<HUNT-ID>
{
  "status": "COMPLETED",
  "verdict": "TRUE_POSITIVE",
  "findings_count": 3,
  "mitre_technique_confirmed": "T1550.002",
  "report_s3_key": "s3://soc-hunt-reports/<HUNT-ID>/report.md"
}
```

### 4.3 Feed Findings into Detection Engineering

For each confirmed True Positive:

1. Open a detection engineering ticket in Jira: `DE-BOARD` with label `hunt-finding`
2. Reference the hunt ID and ATT&CK technique
3. Specify the recommended detection logic (Sigma rule, SIEM query, or EDR policy)
4. Target: detection rule in production within 5 business days for CRITICAL findings, 10 days for HIGH

---

## Phase 5: Posture and Coverage Update

### 5.1 Update ATT&CK Coverage Matrix

After each hunt, update the coverage heatmap:

```bash
soc-cli coverage update \
  --technique T1550.002 \
  --status detected \
  --hunt-id <HUNT-ID> \
  --confidence high
```

### 5.2 Posture Score Contribution

Completed hunts with negative findings (hypothesis not validated) contribute positively to the posture score by increasing ATT&CK coverage confidence. Configure this in the posture scoring engine:

```yaml
# platform/config/posture-weights.yaml
hunt_coverage_bonus:
  per_technique_validated: 0.5  # +0.5 points per validated hunt
  max_bonus: 10.0               # cap at 10 points
```

---

## Hunt Scheduling

Automated hunt schedule (configurable per tenant):

| Frequency | Techniques | Priority |
|---|---|---|
| Weekly | T1003, T1550, T1078, T1059 | HIGH |
| Bi-weekly | T1190, T1566, T1195 | MEDIUM |
| Monthly | All remaining ATT&CK techniques in sector profile | LOW |

To schedule a recurring hunt:

```bash
POST /api/v1/threat-hunts/schedule
{
  "schedule": "0 6 * * MON",
  "hypothesis": "Weekly credential dumping hunt on domain controllers",
  "mitre_technique": "T1003",
  "scope": {"asset_groups": ["domain-controllers"], "timerange_hours": 168}
}
```
