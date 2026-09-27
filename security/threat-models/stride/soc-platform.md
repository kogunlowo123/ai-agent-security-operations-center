# STRIDE Threat Model: AI Agent SOC Platform

## Overview

### System Description
The AI Agent SOC Platform is a multi-tenant system that deploys LLM-powered security agents to perform event ingestion, incident management, posture assessment, and threat hunting. Agents authenticate with short-lived JWTs issued by an Identity Broker, communicate via a LiteLLM gateway to Amazon Bedrock or Vertex AI, and operate under OPA-enforced RBAC policies.

### Assets
| Asset | Sensitivity | Description |
|-------|-------------|-------------|
| Agent JWT tokens | Critical | Grants API access; compromise allows impersonation |
| Tenant security data | Critical | Events, incidents, posture scores |
| LLM inference pipeline | High | Prompt injection could alter agent behavior |
| Identity Broker private key | Critical | Compromise allows forging any agent identity |
| OPA policies | High | Policy bypass allows unauthorized actions |
| SOAR playbook definitions | High | Modification could trigger unauthorized isolations |

---

## STRIDE Analysis

### S — Spoofing

**Threat S1**: Agent token theft via network interception  
**Mitigation**: TLS 1.3 enforced end-to-end; tokens transmitted only over encrypted channels  
**Residual Risk**: Low — requires TLS downgrade attack

**Threat S2**: Forged agent identity (private key compromise)  
**Mitigation**: RSA-4096 private key stored in AWS Secrets Manager with IRSA; key rotation every 90 days; HSM-backed key storage for production  
**Residual Risk**: Medium — privileged AWS role compromise could expose key

---

### T — Tampering

**Threat T1**: OPA policy modification by unauthorized actor  
**Mitigation**: Policies stored in GitOps repo with branch protection; OPA bundle signed and verified at load time; policy changes require peer review  
**Residual Risk**: Low

**Threat T2**: SOAR playbook tampering to trigger unauthorized actions  
**Mitigation**: Playbooks loaded from signed GitOps bundle; execution requires T2 approval for destructive actions  
**Residual Risk**: Low

**Threat T3**: Prompt injection via malicious security event data  
**Mitigation**: Event content sanitized before insertion into LLM prompt; system prompt marked as immutable; output validated against schema before execution  
**Residual Risk**: Medium — novel injection techniques may bypass sanitization

---

### R — Repudiation

**Threat R1**: Agent denies performing a destructive action  
**Mitigation**: Every API call logged to append-only OpenSearch index with agent_id, jti, and action payload; session ledger records all session events  
**Residual Risk**: Low

**Threat R2**: Log tampering to erase evidence  
**Mitigation**: OpenSearch index with write-once policy; logs replicated to S3 with Object Lock (WORM)  
**Residual Risk**: Low

---

### I — Information Disclosure

**Threat I1**: Cross-tenant data leakage via missing tenant filter  
**Mitigation**: OPA `same_tenant` rule enforced on all data-returning endpoints; PostgreSQL RLS policies enforce tenant isolation at the database layer  
**Residual Risk**: Low

**Threat I2**: LLM prompt leaks sensitive tenant data to model provider  
**Mitigation**: Data minimization in prompts; PII redaction layer before LLM calls; contractual data-processing agreements with Anthropic and Google  
**Residual Risk**: Medium — redaction may miss novel PII patterns

---

### D — Denial of Service

**Threat D1**: Token flooding / denial-of-wallet against Bedrock  
**Mitigation**: Per-tenant token budget enforced by Redis-backed TokenBudgetEnforcer; CloudWatch alarm triggers at 1000 invocations/5 min; circuit breaker in LiteLLM router  
**Residual Risk**: Low

**Threat D2**: Excessive hunt launches exhaust system resources  
**Mitigation**: Sigma rule detects >10 hunts/hour; UEBA baseline triggers anomaly alert; T2 approval required for new hunts above threshold  
**Residual Risk**: Low

---

### E — Elevation of Privilege

**Threat E1**: T1 agent exploits API bug to gain T2 scopes  
**Mitigation**: Tier enforced in JWT claims (immutable); OPA `require_t2_or_above` rule checked server-side; no client-side trust for tier  
**Residual Risk**: Low

**Threat E2**: Compromised T2 agent used to manage other agents  
**Mitigation**: `agents:manage` scope requires T2; UEBA monitors scope usage anomalies; session ledger audits all management actions  
**Residual Risk**: Medium — stolen T2 token with agents:manage scope

---

## Residual Risk Summary
| ID | Description | Risk Level | Owner |
|----|-------------|------------|-------|
| S2 | Private key via privileged AWS role | Medium | Platform Team |
| T3 | Prompt injection via event data | Medium | AI Safety Team |
| I2 | PII leakage via LLM prompts | Medium | Privacy Team |
| E2 | Stolen T2 token with agents:manage | Medium | Identity Team |

---

## Review History
| Date | Author | Change |
|------|--------|--------|
| 2025-01-01 | SOC Platform Team | Initial threat model |
