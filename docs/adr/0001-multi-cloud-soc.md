# ADR 0001: Multi-Cloud Security Operations Centre Architecture

**Status:** Accepted  
**Date:** 2024-01-15  
**Deciders:** Platform Engineering, Security Architecture, CTO  
**Supersedes:** N/A  
**Superseded by:** N/A

---

## Context

The AI Agent Security Operations Centre (SOC) must monitor security events from AI agents deployed across multiple cloud environments. The organisation operates:

- **Primary workloads** on AWS (majority of AI agent deployments, EKS clusters, Lambda functions, Bedrock model calls)
- **Data science and analytics** on Azure (Azure ML, Azure OpenAI endpoints)
- **Developer tools and CI/CD** on GCP (Cloud Build, Artifact Registry, GKE for canary deployments)

A cloud-specific SOC approach creates several problems:

1. **Fragmented visibility**: Threats that span clouds (e.g., an agent compromised on AWS exfiltrating data via Azure blob storage) are invisible if each cloud has its own detection pipeline.
2. **Alert fatigue from duplication**: The same threat actor may trigger low-confidence alerts on each platform individually; cross-cloud correlation would produce a single high-confidence incident.
3. **Operational complexity**: Three separate SOC runbooks, toolchains, and on-call rotations increase mean time to detect (MTTD) and mean time to respond (MTTR).
4. **Inconsistent data retention**: Cloud-native SIEM solutions have different retention periods and query APIs, making historical hunting difficult.

The SOC system must ingest CloudEvents from all three providers, normalize them into a canonical event schema, and route them to a unified analysis pipeline without requiring cloud-specific agent deployments for each detection rule.

---

## Decision

**AWS is the primary cloud** for all SOC infrastructure. Azure and GCP are treated as **secondary event sources** whose telemetry is forwarded to the primary AWS-hosted pipeline.

### Architecture

```
┌──────────────┐    CloudEvents     ┌───────────────────────────────┐
│  AWS Sources  │ ─────────────────► │                               │
│  (EKS, Lambda │                    │   AWS SOC Platform (Primary)  │
│   Bedrock)    │                    │                               │
└──────────────┘                    │  ┌─────────────┐              │
                                    │  │  API Gateway │              │
┌──────────────┐    CloudEvents     │  │  + Lambda    │              │
│ Azure Sources │ ─────────────────► │  └──────┬──────┘              │
│ (Azure ML,    │                    │         │                     │
│  Azure OpenAI)│                    │  ┌──────▼──────┐              │
└──────────────┘                    │  │  SQS Queue   │              │
                                    │  │  (ingest)    │              │
┌──────────────┐    CloudEvents     │  └──────┬──────┘              │
│  GCP Sources  │ ─────────────────► │         │                     │
│  (GKE, Cloud  │                    │  ┌──────▼──────────────────┐  │
│   Build)      │                    │  │  Event Processor (ECS)  │  │
└──────────────┘                    │  │  - Normalize             │  │
                                    │  │  - Enrich (MITRE RAG)    │  │
                                    │  │  - Triage                │  │
                                    │  └──────┬──────────────────┘  │
                                    │         │                     │
                                    │  ┌──────▼──────┐  ┌────────┐  │
                                    │  │  PostgreSQL  │  │OpenSearch│ │
                                    │  │  (incidents) │  │(events) │ │
                                    │  └─────────────┘  └────────┘  │
                                    └───────────────────────────────┘
```

### Forwarding Mechanism

- **Azure**: Azure Event Grid subscriptions forward CloudEvents to the SOC API endpoint via HTTPS with HMAC-SHA256 signed payloads.
- **GCP**: Cloud Pub/Sub push subscriptions deliver events to the SOC ingest endpoint.
- All forwarding uses mutual TLS (mTLS) with per-cloud service account certificates.
- A lightweight **event forwarder sidecar** (deployed in each cloud's respective orchestrator) handles batching, retry, and exponential back-off.

### Data Residency

Events containing PII or regulated data are **truncated at source** before forwarding. The forwarding agent applies the PII scrubbing rules defined in `observability/otel/pii-scrub-processor.yaml` before transmission. Raw events with PII remain in each cloud's own storage for the required retention period under local data governance rules.

---

## Consequences

### Positive

- Single pane of glass for all AI agent security events regardless of cloud origin.
- Unified MITRE ATT&CK enrichment pipeline applies consistently across all sources.
- Single on-call rotation and runbook set reduces operational overhead.
- Cross-cloud threat correlation surfaces attacks that would be invisible in siloed monitoring.
- Simpler compliance posture: one SIEM, one audit trail, one retention policy for aggregated events.

### Negative

- **AWS dependency**: a major AWS outage affecting the primary region will degrade SOC capability even for events originating on Azure or GCP. Mitigated by multi-AZ deployment and event buffering at source.
- **Forwarding latency**: events from Azure and GCP incur additional network hop latency (~50–150 ms). Acceptable for SOC use cases where sub-second detection is not required.
- **Egress costs**: forwarding telemetry from Azure and GCP to AWS generates inter-cloud data transfer costs. Estimated at < $500/month at current event volumes.
- **PII truncation complexity**: coordinating PII scrubbing rules across three cloud environments requires a shared configuration distribution mechanism (managed via the `infra/` Terraform modules).

### Neutral

- Each cloud retains its own cloud-native SIEM (CloudTrail Insights, Azure Sentinel, GCP Security Command Centre) for cloud-provider-specific compliance requirements. These are NOT replaced by this SOC; they complement it.
- The multi-cloud forwarding architecture is encapsulated in the `services/event-forwarder/` service and is invisible to downstream SOC components.

---

## Alternatives Considered

### Option A: Federated SOC (rejected)
Run a separate SOC stack per cloud with cross-cloud alerting. Rejected due to tripled operational complexity and inability to correlate cross-cloud events in real time.

### Option B: Azure-Primary (rejected)
Azure Sentinel as the primary SIEM with AWS and GCP forwarding to Azure. Rejected because the majority of AI agent workloads and the team's operational expertise are AWS-centric.

### Option C: SIEM-as-a-Service (e.g., Splunk Cloud, Datadog) (rejected)
Offload to a third-party SIEM. Rejected due to: cost at current event volume, data residency concerns for AI agent telemetry, and inability to run custom MITRE ATT&CK RAG enrichment inline.

---

## References

- [MITRE ATT&CK for Cloud](https://attack.mitre.org/matrices/enterprise/cloud/)
- [CloudEvents Specification v1.0](https://cloudevents.io/)
- [AWS Security Hub cross-account/cross-region architecture](https://docs.aws.amazon.com/securityhub/latest/userguide/finding-aggregation.html)
- ADR 0003: Event-Driven Ingestion Architecture
