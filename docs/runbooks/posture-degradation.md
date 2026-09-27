# Posture Degradation Response Runbook

**Version:** 1.1  
**Owner:** Security Operations Centre  
**Last Updated:** 2024-12-01  
**Review Cadence:** Quarterly  

---

## Overview

This runbook defines the response procedure when the platform's security posture score degrades below defined thresholds. Posture score degradation may indicate an active attack, configuration drift, an accumulation of unresolved findings, or a change in the threat environment.

**Posture Score Scale:**

| Score Range | Rating | Alert Action |
|---|---|---|
| 90–100 | EXCELLENT | No action required |
| 75–89 | GOOD | Weekly review |
| 60–74 | FAIR | Daily review; investigate root cause within 48 h |
| 40–59 | POOR | Immediate investigation; escalate to security lead |
| 0–39 | CRITICAL | Emergency response; escalate to CISO |

**Posture Alerts are triggered when:**
- Score drops below a configured threshold (default: GOOD → FAIR transition, i.e., score < 75)
- Score drops by ≥10 points in any 1-hour window (rapid degradation indicator)
- Any component score (identity, network, data, workload, endpoint) drops to 0

---

## Phase 1: Alert Acknowledgement

### 1.1 Receiving the Alert

Posture degradation alerts arrive via:

- **PagerDuty**: `Posture-Degradation` policy (CRITICAL rating pages immediately; POOR pages within 15 min; FAIR creates a ticket)
- **Slack**: `#soc-posture-alerts` channel
- **Email**: `soc-alerts@acme-corp.com` distribution list

### 1.2 Initial Assessment

```bash
# Get current posture score
GET /api/v1/posture/score?tenant_id=<TENANT>

# Response includes score, rating, trend, components, and recommendations
{
  "score": 48.5,
  "rating": "POOR",
  "trend": "DEGRADING",
  "components": {
    "identity": 20.0,
    "network": 85.0,
    "data": 60.0,
    "workload": 75.0,
    "endpoint": 40.0
  },
  "recommendations": [
    "Review and remediate CRITICAL findings immediately.",
    "Engage incident response team for high-severity events."
  ]
}
```

Identify the **degrading component(s)**:

- **Identity score low** → focus on identity.access.violation events, privilege escalation, credential theft
- **Network score low** → focus on network.anomaly, data exfiltration, C2 beacon events
- **Data score low** → focus on data.access.anomaly, misconfiguration, S3/blob storage events
- **Workload score low** → focus on container escape, malware, lateral movement in compute
- **Endpoint score low** → focus on EDR alerts, persistence mechanisms, suspicious process execution

---

## Phase 2: Root Cause Investigation

### 2.1 Review Contributing Events

```bash
# Get events contributing to posture degradation (last 24 hours, sorted by score impact)
GET /api/v1/posture/contributing-events?tenant_id=<TENANT>&hours=24&severity=CRITICAL,HIGH

# List unresolved incidents driving the posture score down
GET /api/v1/incidents?status=OPEN&severity=CRITICAL,HIGH&tenant_id=<TENANT>
```

### 2.2 Investigate Configuration Drift

Posture degradation may result from cloud misconfiguration rather than an active attack:

```bash
# Check for new misconfigurations
soc-cli posture drift-check --tenant <TENANT> --baseline latest

# Common causes:
# - New S3 bucket created without block-public-access
# - IAM policy attached with * permissions
# - Security group rule opened port 22/3389 to 0.0.0.0/0
# - CloudTrail logging disabled in a region
# - MFA disabled for privileged users
```

### 2.3 Trend Analysis

```bash
# Get posture score history (last 7 days, hourly)
GET /api/v1/posture/history?tenant_id=<TENANT>&interval=1h&days=7
```

Identify the degradation onset time. Cross-reference with:
- Change records (ServiceNow: `https://acme.service-now.com/change`)
- Recent deployments (check CI/CD pipeline logs)
- Incident timeline (was an incident opened around the same time?)

---

## Phase 3: Response by Rating

### CRITICAL Rating (Score 0–39)

**Immediately:**
1. Page the CISO and IR Lead via PagerDuty `CRITICAL-ESCALATION` policy
2. Declare a Security Incident — create incident with severity CRITICAL in the SOC portal
3. Stand up a bridge call: `soc-cli bridge start --incident-id <INC-ID>`
4. Do NOT attempt to remediate alone — require at least 2 responders

**Within 30 minutes:**
5. Identify the top 3 events by severity driving the score
6. Determine if the degradation is caused by an active attack or configuration errors
7. If active attack: follow the Incident Response Runbook (`docs/runbooks/incident-response.md`)
8. If configuration error: proceed to Phase 4 (Remediation)

### POOR Rating (Score 40–59)

**Within 15 minutes:**
1. Notify security lead via Slack DM (do not page)
2. Review all CRITICAL and HIGH open incidents — are they being actively worked?
3. Identify the top contributing events using the API above

**Within 2 hours:**
4. For each unresolved CRITICAL/HIGH incident: verify it has an active assignee and an ETA for containment
5. Identify any quick-win remediations (see Phase 4)
6. Document findings in a posture triage note:

```bash
soc-cli posture note add \
  --tenant <TENANT> \
  --note "Posture POOR (48.5). Root cause: 3 unresolved CRITICAL incidents (INC-001, INC-002, INC-003). Identity component at 20% due to pass-the-hash campaign. IR team engaged. ETA containment: 4 hours."
```

### FAIR Rating (Score 60–74)

**Within 2 hours:**
1. Review contributing events and open incidents
2. Check for configuration drift using `drift-check` above
3. Review AI-generated recommendations in the posture score response

**Within 48 hours:**
4. Create remediation tickets for each identified gap
5. Verify that detection rules cover the contributing event types

---

## Phase 4: Remediation

### 4.1 Quick Wins (< 30 min each)

**Misconfigured S3 bucket:**
```bash
aws s3api put-public-access-block \
  --bucket <BUCKET> \
  --public-access-block-configuration "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"
```

**Overly permissive security group:**
```bash
aws ec2 revoke-security-group-ingress \
  --group-id <SG_ID> \
  --protocol tcp \
  --port 22 \
  --cidr 0.0.0.0/0
```

**Re-enable CloudTrail in a region:**
```bash
aws cloudtrail start-logging --name <TRAIL_NAME> --region <REGION>
```

**Enforce MFA for privileged users:**
```bash
# AWS IAM Identity Centre — attach MFA enforcement policy
soc-cli identity enforce-mfa --group "privileged-users" --provider aws-sso
```

### 4.2 Resolve Contributing Incidents

For each open CRITICAL/HIGH incident contributing to the posture score:
1. Confirm active remediation is in progress
2. If stale (no updates > 2 hours on CRITICAL, > 8 hours on HIGH): reassign and escalate

### 4.3 Update False Positive Registry

If false positives are inflating the event count driving down the posture score:

```bash
soc-cli fp-registry add \
  --event-type "network.port_scan.detected" \
  --source-ip "10.0.0.50" \
  --justification "Authorised internal security scanner — Change #CHG-2024-0892" \
  --expiry "2025-01-01T00:00:00Z"
```

---

## Phase 5: Verification and Closure

### 5.1 Verify Score Recovery

After applying remediations, monitor the posture score:

```bash
# Poll posture score every 5 minutes during recovery
watch -n 300 'soc-cli posture score --tenant <TENANT>'
```

Score recovery timeline expectations:
- After resolving a CRITICAL incident: expect +20–30 points within 1 score calculation cycle (default: 15 min)
- After fixing configuration drift: expect +5–15 points
- After clearing FP noise: variable, depending on FP volume

### 5.2 Post-Degradation Report

For any POOR or CRITICAL degradation event, complete a posture recovery report within 24 hours:

```markdown
## Posture Degradation Report — <DATE>

**Tenant:** <TENANT>
**Lowest Score:** <SCORE> (<RATING>)
**Duration Below GOOD:** <HH:MM>
**Root Cause:** <DESCRIPTION>
**Contributing Events:** <LIST>
**Actions Taken:** <LIST>
**Score at Closure:** <SCORE>
**Preventive Measures:** <LIST>
```

### 5.3 Update Posture Thresholds (if needed)

If the alert threshold is generating too many false positives (legitimate changes triggering alerts):

```bash
# Update alert threshold for tenant
soc-cli posture config set \
  --tenant <TENANT> \
  --alert-threshold 65 \
  --rapid-degradation-threshold 15
```

Document the rationale in the tenant configuration audit log.

---

## Escalation Matrix

| Condition | Escalate To | Method |
|---|---|---|
| Score CRITICAL (<40) | CISO + IR Lead | PagerDuty |
| Score POOR (<60) for > 4 hours | Security Lead | Slack DM |
| Score degrading during active incident | Incident Commander | Bridge call |
| Unknown root cause after 2 hours | Senior Security Architect | Slack |
| Data component critical + PII involved | Legal + Privacy | Email + Slack |
