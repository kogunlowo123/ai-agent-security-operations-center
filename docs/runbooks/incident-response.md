# Incident Response Runbook

**Version:** 2.1  
**Owner:** Security Operations Centre  
**Last Updated:** 2024-12-01  
**Review Cadence:** Quarterly  

---

## Overview

This runbook defines the end-to-end incident response procedure for the AI Agent SOC platform. It covers all phases from initial detection through post-incident closure. All SOC personnel must be familiar with this document before being granted on-call rotation privileges.

**Severity Definitions:**

| Severity | Definition | Response SLA |
|---|---|---|
| CRITICAL | Active attack, ransomware, data exfiltration, production outage | 15 min acknowledge / 1 hr containment |
| HIGH | Confirmed compromise, privilege escalation, credential theft | 30 min acknowledge / 4 hr containment |
| MEDIUM | Suspicious activity, policy violation, anomaly requiring investigation | 2 hr acknowledge / 24 hr investigation |
| LOW | Informational alert, compliance finding | 24 hr acknowledge / 72 hr investigation |

---

## Phase 1: Detection

### 1.1 Automated Detection

The SOC platform automatically creates incidents for CRITICAL and HIGH events via the triage agent. Analysts receive:

- **PagerDuty alert** with incident link and AI-generated triage summary
- **Slack notification** to `#soc-incidents` (CRITICAL: `@here`; HIGH: thread only)
- **Email** to the on-call analyst

### 1.2 Manual Report Intake

If a user or system reports a potential incident not yet detected:

1. Navigate to the SOC portal: `https://soc.internal.acme-corp.com`
2. Click **"Create Incident"** → select severity → fill in description
3. Assign to yourself if you are taking ownership
4. Proceed to Phase 2

### 1.3 False Positive Triage

Before escalating, verify the alert is not a known false positive:

1. Check the **event type** against the False Positive Registry (`/api/v1/false-positive-registry`)
2. Review the AI triage agent's confidence score — scores below 0.60 warrant additional scrutiny
3. If the event matches a known FP pattern, close with status `FALSE_POSITIVE` and add justification notes

---

## Phase 2: Triage

### 2.1 Acknowledge the Incident

```bash
# CLI
soc-cli incident ack --incident-id <INC-ID>

# API
PATCH /api/v1/incidents/<INC-ID>/status
{"status": "IN_PROGRESS", "notes": "Analyst [name] acknowledging at [time]"}
```

### 2.2 Gather Initial Context

Within 15 minutes of acknowledgement, collect:

- [ ] **Source of the alert**: which detection rule / event type triggered it?
- [ ] **Affected entity**: user account, service account, workload, data asset?
- [ ] **Temporal context**: when did this start? Is it ongoing?
- [ ] **Scope**: how many assets/accounts/systems are involved?
- [ ] **MITRE ATT&CK mapping**: what technique does this most closely resemble? (AI triage agent provides initial mapping — verify against ATT&CK)

### 2.3 Assess Initial Severity

Re-assess the AI-assigned severity based on gathered context. Escalate or downgrade as appropriate. Document the rationale in the incident notes.

**Escalate when:**
- Active data exfiltration (bytes > 100 MB to unknown external IPs)
- Domain controller or identity provider compromise
- Ransomware indicators (mass encryption, shadow copy deletion)
- Critical system availability impact (>P2 production service)
- Regulatory breach threshold reached (e.g., GDPR 72-hour notification clock starts)

---

## Phase 3: Containment

### 3.1 Short-Term Containment

Apply the minimum necessary containment action to stop active harm without destroying evidence:

**Identity compromise:**
```bash
# Disable compromised account (Azure AD)
az ad user update --id <upn> --account-enabled false

# Revoke AWS access keys
aws iam delete-access-key --access-key-id <KEY_ID> --user-name <USER>

# Revoke GCP service account keys
gcloud iam service-accounts keys disable <KEY_ID> --iam-account <SA_EMAIL>
```

**Network isolation (EKS):**
```bash
# Apply deny-all NetworkPolicy to compromised pod namespace
kubectl apply -f deploy/scripts/containment/deny-all-netpol.yaml -n <NAMESPACE>
```

**S3 data exfiltration — block public access:**
```bash
aws s3api put-public-access-block \
  --bucket <BUCKET_NAME> \
  --public-access-block-configuration "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"
```

### 3.2 Evidence Preservation

**Before** making any changes, preserve:

1. **Memory forensics** (if live malware suspected): capture volatile memory via EDR console
2. **Disk image**: snapshot EBS volume(s) before terminating instances
3. **CloudTrail logs**: confirm the relevant time window is captured (CloudTrail has 90-day default retention; export to S3 for long-term preservation)
4. **Network flow logs**: export VPC Flow Logs for the affected subnet for the relevant time window
5. **Application logs**: ship to S3 via the SOC platform log archive endpoint

```bash
soc-cli evidence preserve \
  --incident-id <INC-ID> \
  --resource <RESOURCE_ARN> \
  --time-from <ISO8601> \
  --time-to <ISO8601>
```

### 3.3 Long-Term Containment

Apply persistent controls that survive the investigation:

- Rotate all credentials (passwords, API keys, certificates) for affected accounts
- Deploy updated WAF/security group rules
- Enable enhanced logging on affected systems
- Add IOCs (IP, domain, hash) to blocklists

---

## Phase 4: Investigation

### 4.1 Launch Threat Hunt

```bash
# Via API
POST /api/v1/threat-hunts
{
  "hypothesis": "Lateral movement from compromised workstation to domain controllers via T1550.002",
  "incident_id": "<INC-ID>",
  "scope": {
    "timerange_hours": 72,
    "asset_groups": ["domain-controllers", "file-servers"]
  }
}
```

### 4.2 SIEM Query Templates

Common investigation queries (adjust time range as needed):

**Identity: All actions by a compromised user in last 72 hours:**
```sql
GET soc-events-*/_search
{
  "query": {
    "bool": {
      "must": [
        {"term": {"data.actor": "<USER>"}},
        {"range": {"time": {"gte": "now-72h"}}}
      ]
    }
  },
  "sort": [{"time": "desc"}]
}
```

**Network: All outbound connections from affected host:**
```sql
GET soc-events-*/_search
{
  "query": {
    "bool": {
      "must": [
        {"term": {"data.source_host": "<HOSTNAME>"}},
        {"term": {"event_type": "network.connection"}},
        {"range": {"time": {"gte": "now-24h"}}}
      ]
    }
  }
}
```

### 4.3 Document Findings

For each investigation finding, add a note to the incident:

```bash
soc-cli incident note add \
  --incident-id <INC-ID> \
  --note "Found C2 beacon to 198.51.100.77:443 from WORKSTATION-042 at 2024-12-01T03:17:00Z. Consistent with T1071.001."
```

---

## Phase 5: Eradication

1. **Remove malware / backdoors**: use EDR console to quarantine malicious files; validate with hash verification
2. **Rebuild compromised systems**: terminate and re-provision from golden AMI where feasible
3. **Patch vulnerabilities**: apply relevant patches or workarounds that contributed to the compromise
4. **Remove unauthorised access**: delete rogue accounts, revoke unauthorised IAM policies, remove persistence mechanisms
5. **Update detection rules**: ensure the attack technique is covered by a detection rule or ATT&CK technique in the corpus

---

## Phase 6: Recovery

1. **Restore from clean backup** if data was corrupted or encrypted
2. **Validate system integrity** before returning to production:
   - File integrity check (FIM baseline comparison)
   - EDR clean bill of health
   - Network traffic normalisation confirmed
3. **Gradually restore access**: re-enable accounts one by one with enhanced monitoring
4. **Monitor for re-compromise**: heightened alert threshold for 30 days on affected assets
5. **Update the incident status** to `RESOLVED` when production confidence is high

---

## Phase 7: Post-Incident Activities

### 7.1 Close the Incident

```bash
PATCH /api/v1/incidents/<INC-ID>/status
{
  "status": "CLOSED",
  "resolution": "REMEDIATED",
  "resolution_notes": "Compromised account isolated, backdoor removed, patch applied. Root cause: phishing email with malicious macro.",
  "mttr_hours": 6.5
}
```

### 7.2 Post-Incident Review (PIR)

**Required for CRITICAL incidents:** PIR must be completed within 5 business days.  
**Required for HIGH incidents:** PIR required if MTTR > SLA or if novel attack technique.

PIR template: `docs/templates/post-incident-review.md`

PIR must cover:
- Timeline of events
- Detection gap analysis: why wasn't this caught earlier?
- ATT&CK coverage gaps
- Runbook improvements
- Posture recommendations (feed into next posture score cycle)

### 7.3 Lessons Learned → Platform Improvements

Open a Jira ticket for each platform improvement identified. Tag with `soc-platform` and the incident ID.

---

## Escalation Contacts

| Role | Contact | Availability |
|---|---|---|
| SOC Lead | `soc-lead@acme-corp.com` / PD: `SOC-Lead` | Business hours |
| On-call IR Lead | PagerDuty escalation policy `IR-LEAD` | 24/7 |
| CISO | `ciso@acme-corp.com` | CRITICAL only |
| Legal (breach notification) | `legal-privacy@acme-corp.com` | CRITICAL with PII confirmed |
| AWS Support | Console → Support Centre → Case (Business/Enterprise support) | 24/7 |

---

## Break-Glass Access

If production access is required outside normal IAM controls, use the break-glass script:

```bash
bash deploy/scripts/break_glass.sh --reason "Active incident INC-2024-0892" --incident-id INC-2024-0892
```

The script creates time-limited (4-hour) admin credentials, logs the access to the audit trail, and pages the CISO.
