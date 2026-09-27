# ADR 0003: CloudEvents-Based Event-Driven Ingestion Architecture

**Status:** Accepted  
**Date:** 2024-12-01  
**Deciders:** Platform Engineering, Security Architecture  
**Supersedes:** N/A  
**Superseded by:** N/A

---

## Context

The SOC platform ingests security telemetry from dozens of sources: cloud provider audit logs, identity providers, EDR agents, network sensors, CI/CD pipelines, and custom application instrumentation. At current scale this is approximately:

- **Peak ingestion rate**: 85,000 events/second (projected 200,000/s in 18 months)
- **Average event size**: 1.2 KB
- **Median ingestion latency requirement**: ≤10 s from event emission to SIEM availability
- **P99 latency requirement**: ≤30 s
- **Sources**: 47 distinct source types across 3 cloud providers

The previous architecture used a pull-based polling model: each source was polled on a schedule (30 s – 5 min intervals depending on source type). This introduced:
1. Detection latency directly proportional to poll interval.
2. "N+1" polling fan-out as new sources were onboarded.
3. Schema heterogeneity: each source had a bespoke payload schema, requiring per-source ETL.
4. No standard for mandatory event metadata (source attribution, time, tenant scoping).

We evaluated:

| Option | Notes | Decision |
|---|---|---|
| Polling (current) | Simple but high latency | Rejected |
| Proprietary push webhooks | Per-vendor schema divergence | Rejected |
| Apache Kafka (self-managed) | High ops burden, overkill at current scale | Rejected |
| **CloudEvents v1.0 + SQS/Kinesis** | Open standard, AWS-native scaling | **Selected** |
| OCSF (Open Cybersecurity Schema Framework) | Good schema, but no transport standard | Partial adoption (OCSF for normalised schema inside CloudEvent `data`) |

## Decision

Adopt **CloudEvents v1.0** as the mandatory envelope schema for all events entering the SOC platform. Use **Amazon Kinesis Data Streams** as the primary transport and **Amazon SQS** for agent job queues.

### CloudEvents Envelope

Every event entering the platform must conform to CloudEvents v1.0:

```json
{
  "specversion": "1.0",
  "id": "<uuid-v4>",
  "source": "github.com/acme-corp/backend",
  "type": "identity.access.violation",
  "tenant_id": "<tenant-uuid>",
  "datacontenttype": "application/json",
  "time": "2024-12-01T14:32:11.000Z",
  "data": {
    "severity": "CRITICAL",
    "actor": "svc-account@example.com",
    "resource": "arn:aws:iam:::role/AdminRole",
    "description": "..."
  }
}
```

Required attributes beyond the CloudEvents core spec:
- `tenant_id` (extension): multi-tenancy isolation key — validated against caller's JWT.
- `type` (must be in registered event type registry — see `platform/registry/event_types.yaml`).
- `source` (must be in registered source registry — see `platform/registry/sources.yaml`).

### Transport Architecture

```
Source → CloudEvents HTTP POST → API Gateway → Kinesis Data Streams
                                                     │
                                          ┌──────────┴──────────┐
                                          │   Kinesis Consumer   │
                                          │  (Lambda / EKS pod)  │
                                          └──────────┬──────────┘
                                                     │
                                     ┌───────────────┼───────────────┐
                                     │               │               │
                                 OpenSearch       SQS Queue       DynamoDB
                                 (SIEM store)   (Agent jobs)    (Incident DB)
```

- **Kinesis Data Streams**: 24-hour retention, 1,000 shards (auto-scaled based on ingestion rate). Shard key = `tenant_id` to ensure per-tenant ordering.
- **SQS FIFO Queue** for agent job dispatch (threat hunt, triage): exactly-once delivery, deduplication by `event_id`.
- **API Gateway** validates CloudEvents envelope schema before forwarding to Kinesis. Invalid events return 422 with field-level error details. Invalid source or type returns 422 (not 400 — schema validation failure, not auth failure).

### Schema Validation

The ingestion API validates:
1. CloudEvents core required fields (specversion, id, source, type, time, datacontenttype).
2. `tenant_id` extension matches the caller's JWT claim.
3. `type` is in the registered event type registry.
4. `source` is in the registered source registry.
5. `data` content-type matches `datacontenttype`.

Validation failures are logged to a dead-letter stream (`soc-invalid-events-dlq`) with the rejection reason for debugging.

### Normalisation (OCSF)

Inside the `data` field, all events are normalised to **Open Cybersecurity Schema Framework (OCSF)** class schemas (e.g. class 3002 for Authentication events). This normalisation happens at the Kinesis consumer stage, not at ingestion — the raw CloudEvent is stored unchanged in the DLQ and in a raw S3 archive, preserving forensic fidelity.

## Consequences

### Positive
- **Latency**: median event-to-SIEM latency drops from ~90 s (polling) to <10 s (push + streaming).
- **Extensibility**: new event sources onboard by registering a `source` entry and mapping to a CloudEvents translator — no changes to the consumer pipeline.
- **Schema contract**: the CloudEvents envelope enforces minimum metadata (time, source, type, tenant_id) at the API boundary — downstream consumers can depend on these fields.
- **Vendor portability**: CloudEvents is a CNCF standard. If we migrate from Kinesis to Azure Event Hub or Pub/Sub, the event schema is unchanged.
- **Audit trail**: every event has a globally unique `id` (UUID v4), enabling correlation across log systems.

### Negative / Risks
- **Source onboarding cost**: 47 existing sources must be wrapped with a CloudEvents adapter. Estimated effort: 2 weeks per engineer for 3 engineers.
  - Mitigated by: SDK provided in `platform/sdk/python/` and `platform/sdk/go/` with CloudEvents helpers.
- **Kinesis shard management**: over-sharding wastes cost; under-sharding causes throttling.
  - Mitigated by: auto-scaling policy triggered on `IncomingRecords` CloudWatch metric; alert at 70% shard utilisation.
- **SQS FIFO throughput limit**: 3,000 TPS per queue.
  - Mitigated by: per-tenant SQS FIFO queue for high-volume tenants; shared queue for low-volume tenants.
- **CloudEvents 1.0 does not encrypt data fields**: PII may be present in `data`.
  - Mitigated by: TLS in transit (mandatory); PII scanner at Kinesis consumer removes/tags PII before OpenSearch indexing; raw events in S3 encrypted at rest with KMS CMK.

### Neutral
- OCSF normalisation is applied post-ingestion. Some downstream consumers (e.g., legacy SIEM integrations) still receive raw CloudEvent `data` payloads and handle normalisation themselves.
- CloudEvents HTTP binding is used for all sources. Binary content mode is not used (all payloads are JSON).

## Review Date

This ADR is subject to review when ingestion rate consistently exceeds 150,000 events/second (Kinesis scaling evaluation required) or when CloudEvents v2.0 is ratified by CNCF.

Next scheduled review: 2025-06-01.
