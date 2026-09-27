# Posture Score Degradation Runbook

**Version:** 1.0  
**Owner:** SOC Platform Team  
**Last Updated:** 2024-01-25  
**Applies To:** Security posture score degradation events (any tenant)

---

## Overview

The SOC platform computes a security posture score (`GET /api/v1/posture/score`) ranging from 0–100 across six weighted components: Identity (25%), Policy (20%), Runtime (20%), Supply Chain (15%), SDLC (10%), and Mesh (10%).

A posture degradation event is triggered when:
- The overall score drops by **≥ 5 points** in a 24-hour rolling window, OR
- Any single component score drops by **≥ 10 points**, OR
- The overall score falls below the rating threshold boundaries:
  - EXCELLENT → GOOD (≥ 90 → < 90)
  - GOOD → FAIR (≥ 75 → < 75)
  - FAIR → POOR (≥ 60 → < 60)
  - POOR → CRITICAL (≥ 40 → < 40)

Degradation events are delivered as PagerDuty LOW/MEDIUM priority alerts (CRITICAL incidents use the standard incident response runbook).

---

## Step 1: Acknowledge and Characterise the Degradation

### 1.1 Get Current Posture Score

```bash
curl -H "Authorization: Bearer $TOKEN" \
  -H "X-Tenant-ID: $TENANT" \
  https://soc.internal/api/v1/posture/score | jq .
```

Note:
- `overall_score`: Current score (0–100)
- `rating`: `EXCELLENT`, `GOOD`, `FAIR`, `POOR`, or `CRITICAL`
- `trend`: `IMPROVING`, `STABLE`, or `DEGRADING`
- `component_scores`: Per-component breakdown
- `recommendations`: Auto-generated remediation steps

### 1.2 Identify the Degraded Component(s)

```bash
# Get component-level detail with historical comparison
curl -H "Authorization: Bearer $TOKEN" \
  "https://soc.internal/api/v1/posture/score?history=true&hours=48" | \
  jq '.component_scores[] | select(.trend == "DEGRADING")'
```

### 1.3 Check for Correlated Incidents

Posture degradation is often a lagging indicator of an active incident:

```bash
# Check for open incidents in the last 48 hours
curl -H "Authorization: Bearer $TOKEN" \
  "https://soc.internal/api/v1/incidents?status=OPEN,IN_PROGRESS&hours=48" | \
  jq '.items[] | {id, severity, title, created_at}'
```

If open incidents exist with severity HIGH or CRITICAL, **switch to the Incident Response Runbook** and handle the incident first.

---

## Step 2: Root Cause Analysis by Component

### Component: Identity (weight: 25%)

Score degradation in the Identity component indicates issues in `ai-agent-identity-governance`.

**Common causes and checks:**

| Cause | Investigation Command |
|-------|----------------------|
| Increase in identity.access.violation events | `GET /api/v1/events?type=identity.access.violation&hours=24` |
| New agents without proper IAM role assignment | Check identity-governance for agents missing role bindings |
| Stale or over-privileged service accounts | Review IAM policy drift reports |
| Failed MFA events | `GET /api/v1/events?type=auth.mfa.failure&hours=24` |

**Remediation:**
```bash
# Trigger identity posture re-evaluation after fixing IAM issues
curl -X POST https://identity-governance.internal/api/v1/posture/recompute \
  -H "Authorization: Bearer $TOKEN"
```

### Component: Policy (weight: 20%)

Score degradation in the Policy component indicates issues in `ai-agent-policy-enforcement`.

**Common causes:**
- Policy violations by AI agents (accessing resources outside their authorised scope)
- Policy definition gaps (new agent capabilities without corresponding policies)
- Policy engine downtime causing bypass events

**Investigation:**
```bash
curl "https://soc.internal/api/v1/events?type=policy.violation&hours=24&severity=HIGH,CRITICAL" \
  -H "Authorization: Bearer $TOKEN" | jq '.items | length'
```

### Component: Runtime (weight: 20%)

Score degradation in the Runtime component indicates issues in `ai-agent-runtime-security`.

**Common causes:**
- Anomalous syscall patterns from agent containers
- Container escape attempts
- Unexpected network connections from agent pods

**Investigation:**
```bash
# Check runtime anomaly events
curl "https://soc.internal/api/v1/events?type=runtime.anomaly&hours=24" \
  -H "Authorization: Bearer $TOKEN"

# Check Falco alerts (if integrated)
kubectl get events -n agent-runtime --field-selector reason=FalcoAlert
```

### Component: Supply Chain (weight: 15%)

Score degradation in Supply Chain indicates issues in `ai-agent-supply-chain-security`.

**Common causes:**
- New CVEs in agent dependencies above CVSS 7.0
- Dependency version drift (agents using versions different from approved baseline)
- Compromised package detected in agent runtime

**Investigation:**
```bash
# Check supply chain events
curl "https://soc.internal/api/v1/events?type=supply_chain.*&hours=24" \
  -H "Authorization: Bearer $TOKEN"
```

**Remediation:**
- Update affected packages: coordinate with DevOps for rolling deployment
- If actively exploited CVE: consider taking the affected agent offline

### Component: SDLC (weight: 10%)

Score degradation in SDLC indicates issues in `ai-agent-sdlc-security`.

**Common causes:**
- SAST/DAST findings above threshold in recent deployments
- Secrets committed to repository
- Unsigned build artifacts in production

**Investigation:**
```bash
# Check SDLC events
curl "https://soc.internal/api/v1/events?type=ci_cd.*&hours=24&severity=HIGH,CRITICAL" \
  -H "Authorization: Bearer $TOKEN"
```

### Component: Mesh (weight: 10%)

Score degradation in the Mesh component indicates issues in `ai-agent-service-mesh-security`.

**Common causes:**
- mTLS failures between services (authentication errors)
- Unexpected service-to-service communication (policy violations in the mesh)
- Service mesh control plane connectivity issues

**Investigation:**
```bash
# Check mesh events
curl "https://soc.internal/api/v1/events?type=mesh.*&hours=24" \
  -H "Authorization: Bearer $TOKEN"

# Check Istio/Envoy logs
kubectl logs -n istio-system deployment/istiod --tail=100 | grep ERROR
```

---

## Step 3: Remediation

### 3.1 Immediate Containment

If the posture score is CRITICAL (< 40) or POOR (< 60) and actively degrading:

1. **Activate enhanced monitoring**: Reduce the posture score refresh interval from 1 hour to 5 minutes:
   ```bash
   curl -X POST https://soc.internal/api/v1/posture/config \
     -H "Authorization: Bearer $ADMIN_TOKEN" \
     -d '{"refresh_interval_seconds": 300}'
   ```

2. **Freeze non-critical agent deployments**: Prevent new agent versions from being deployed while posture is CRITICAL:
   ```bash
   # Apply deployment freeze annotation to CI/CD pipeline
   kubectl annotate namespace agent-runtime soc.deployment-freeze=true
   ```

3. **Notify asset owners**: Alert the responsible team for each degraded component.

### 3.2 Root Cause Remediation

Follow the component-specific remediation steps in Step 2 for each degraded component.

### 3.3 Verify Recovery

After applying remediations, force a posture score refresh and verify improvement:

```bash
# Force immediate posture score recompute
curl -X POST https://soc.internal/api/v1/posture/score/refresh \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Tenant-ID: $TENANT"

# Wait 60 seconds, then check the new score
sleep 60
curl -H "Authorization: Bearer $TOKEN" \
  https://soc.internal/api/v1/posture/score | jq '{overall_score, rating, trend}'
```

The score should show `"trend": "IMPROVING"` within 2–3 refresh cycles.

---

## Step 4: Post-Degradation Actions

### 4.1 Document the Degradation

For degradation events lasting > 4 hours or crossing a rating boundary:

```bash
# Create a posture-degradation report
cat > /tmp/posture-report-$(date +%Y%m%d).md << EOF
# Posture Degradation Report - $(date +%Y-%m-%d)
## Affected Tenant: $TENANT
## Duration: $START_TIME to $END_TIME
## Score Range: $MIN_SCORE to $CURRENT_SCORE
## Components Affected: $COMPONENTS
## Root Cause: ...
## Remediation Actions: ...
## Prevention: ...
EOF
```

### 4.2 Update Detection Rules

If the degradation was caused by a new threat pattern not previously covered by detection rules:

1. Create a new detection rule in `services/api/src/rules/`
2. Add corresponding tests to `tests/unit/test_detection_rules.py`
3. Submit for review: `gh pr create --base main --title "feat: add detection rule for [pattern]"`

### 4.3 Posture Improvement Tasks

The posture score recommendations (`GET /api/v1/posture/score` → `recommendations` field) provide a prioritised backlog of improvements. Create Jira/Linear tickets for each unresolved recommendation with severity MEDIUM or higher.

---

## Escalation Thresholds

| Condition | Escalation Target | Method |
|-----------|------------------|--------|
| Score < 40 (CRITICAL) | SOC Lead + CISO | PagerDuty + Slack #soc-critical |
| Score drops > 20 points in 1h | SOC Lead | PagerDuty |
| Score < 60 for > 24h | Engineering Lead | Slack #soc-alerts + Jira |
| Supply chain component < 50 | CISO + Legal | Email + Slack |

---

## Reference: Posture Score Calculation

The overall posture score is computed as:

```
overall = (identity × 0.25) + (policy × 0.20) + (runtime × 0.20) +
          (supply_chain × 0.15) + (sdlc × 0.10) + (mesh × 0.10)
```

Each component score is calculated from event counts over a 24-hour rolling window:
- Base score: 100
- Deductions: −5 per HIGH event, −10 per CRITICAL event (capped at −60 per component)
- Bonuses: +2 per 24-hour period with zero HIGH/CRITICAL events (up to +10)
