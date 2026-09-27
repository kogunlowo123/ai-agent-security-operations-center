# ADR 0003: CloudEvents-Based Event-Driven Ingestion Architecture

**Status:** Accepted  
**Date:** 2024-02-01  
**Deciders:** Platform Engineering, Security Architecture  
**Supersedes:** N/A

---

## Context

The SOC platform must ingest security telemetry from nine source repositories spanning identity governance, policy enforcement, runtime monitoring, supply chain security, service mesh observability, SDLC integrity, model security, multi-cloud compliance, and network security. Each source repository emits security-relevant events at different rates, in different formats, and with different reliability characteristics.

Key requirements:
- **Schema evolution**: Source repositories evolve independently; the ingest pipeline must tolerate schema additions without breaking.
- **Back-pressure**: A compromised agent may flood the pipeline with millions of events; the ingest layer must protect downstream processors.
- **Delivery guarantees**: CRITICAL severity events must not be lost even during downstream processing failures.
- **Multi-tenancy**: Events from different customer tenants must be isolated at the ingestion layer — a tenant A event must never be processed by tenant B's pipeline.
- **Auditability**: Every event ingested must be traceable from source to incident (or dismissal), with a complete audit trail.
- **Cross-cloud compatibility**: Sources running on AWS, Azure, and GCP must be able to emit events using a single protocol without cloud-specific SDKs.

---

## Decision

**Adopt the CloudEvents v1.0 specification** as the canonical event envelope format for all SOC ingest traffic, with AWS SQS as the durable queue backing the ingest pipeline.

### Protocol

All source repositories emit events as CloudEvents v1.0 JSON objects delivered over HTTPS to the SOC ingest endpoint (`POST /api/v1/events/ingest`). The CloudEvents envelope provides:

- `specversion`: Always `"1.0"`
- `id`: UUID v4, used for idempotent deduplication (events with a previously seen `id` are dropped with HTTP 200)
- `source`: Identifies the emitting repository (e.g., `"ai-agent-identity-governance/v1"`)
- `type`: Hierarchical event type following the reverse-DNS convention (e.g., `"identity.access.violation"`, `"runtime.anomaly.detected"`)
- `time`: RFC 3339 timestamp of when the event occurred at source (not when it was received)
- `datacontenttype`: `"application/json"`
- `data`: Event-specific payload conforming to the source repository's schema

### Canonical Event Schema Extension Attributes

The following CloudEvents extension attributes are required by the SOC platform:

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `tenantid` | string | Yes | Customer tenant identifier for multi-tenant isolation |
| `severity` | string | Yes | `LOW`, `MEDIUM`, `HIGH`, `CRITICAL` |
| `sourcerepo` | string | Yes | Short name of the source repository |
| `principalid` | string | No | AI agent or user identity that triggered the event |

### Ingest Pipeline

```
Source Repo            SOC API              SQS                Event Processor
    │                    │                   │                        │
    │  POST /events/ingest│                   │                        │
    │ ──────────────────► │                   │                        │
    │                    │ Validate schema     │                        │
    │                    │ Extract tenant_id   │                        │
    │                    │ Deduplicate by id   │                        │
    │                    │ ──────────────────► │                        │
    │  HTTP 200 + event_id│ SQS SendMessage    │                        │
    │ ◄────────────────── │                   │  SQS ReceiveMessage    │
    │                    │                   │ ──────────────────────► │
    │                    │                   │                   Enrich + Triage
    │                    │                   │                   MITRE RAG
    │                    │                   │                   Create Incident
    │                    │                   │  DeleteMessage         │
    │                    │                   │ ◄────────────────────── │
```

### SQS Configuration

- **Queue type**: Standard (at-least-once delivery)
- **Visibility timeout**: 120 seconds (covers 2× worst-case processing time)
- **Message retention**: 4 days
- **DLQ**: Separate dead-letter queue (`soc-ingest-dlq`) with retention 14 days; alerts fire if DLQ depth > 0
- **Deduplication**: Implemented at the API layer using a Redis cache of recent event IDs (TTL: 24 hours). SQS Standard queue does not guarantee exactly-once delivery; the processor is idempotent.
- **Message attributes**: `TenantId` and `Severity` are set as SQS message attributes to enable per-tenant and per-severity queue policies in the future without re-parsing the body.

### Back-pressure

The SQS queue provides natural back-pressure. The event processor scales horizontally via ECS auto-scaling based on the `ApproximateNumberOfMessagesVisible` CloudWatch metric. Maximum concurrency is capped at 50 ECS tasks to prevent overwhelming the PostgreSQL and OpenSearch backends.

### Schema Validation

CloudEvent schema validation is performed at the API layer using `pydantic` v2 models. Invalid events (missing required fields, wrong types) are rejected with HTTP 422 and never enter the queue. Validation errors are logged with the raw payload for forensic analysis.

---

## Consequences

### Positive

- **Cloud-agnostic**: Sources on any cloud can emit CloudEvents over HTTPS without cloud-specific SDKs. Azure Event Grid and GCP Pub/Sub natively support CloudEvents.
- **Decoupled**: The ingest API and event processor are independently deployable and scalable.
- **Durable**: SQS persists messages for 4 days; events survive processor outages.
- **Back-pressure resilient**: Message accumulation in SQS protects downstream processors; the API remains responsive during spikes.
- **Idempotent**: UUID-based deduplication prevents duplicate incident creation from retry storms.
- **Observable**: Every event gets a unique `event_id` returned to the caller, enabling end-to-end tracing from source to incident via the `X-Correlation-ID` header.

### Negative

- **At-least-once semantics**: Events may be processed more than once during SQS visibility timeout races. All processors must be idempotent (enforced via database unique constraints on `event_id`).
- **No strict ordering**: SQS Standard does not guarantee FIFO ordering. Events from the same agent may be processed out of order. Acceptable for SOC use cases where event order is tracked via the `time` field, not processing order.
- **Polling overhead**: SQS long polling (20s) means up to 20-second latency from event receipt to processor start. Acceptable for SOC; sub-second detection is handled by the streaming analytics pipeline (separate ADR).
- **CloudEvents adoption burden**: Source repositories must adopt the CloudEvents SDK or envelope format. Mitigated by providing a thin wrapper library (`packages/soc-event-emitter`) that handles envelope construction.

### Neutral

- The CloudEvents `type` field is used for routing rules in the processor — different event types trigger different enrichment and triage logic.
- Future consideration: migrate high-volume event types to Amazon Kinesis for sub-second latency if the 20-second SQS polling latency proves insufficient.

---

## Alternatives Considered

### Option A: Direct HTTP from source to processor (rejected)
No message durability. A processor restart loses all in-flight events. Back-pressure requires complex rate limiting at the API layer.

### Option B: Apache Kafka (rejected)
Kafka provides better ordering guarantees and replay capability, but requires significant operational overhead (cluster management, ZooKeeper/KRaft, schema registry). At current event volumes (<10k/day), Kafka's operational cost outweighs its benefits. Re-evaluate if volume exceeds 1M events/day.

### Option C: AWS EventBridge (rejected)
EventBridge natively supports CloudEvents routing but has a 256 KB event size limit, which conflicts with certain AI agent telemetry payloads (model input/output logs can be large). Also, EventBridge has higher per-event costs at scale than SQS.

### Option D: Proprietary binary protocol (rejected)
A custom binary protocol would reduce bandwidth but breaks cloud-agnostic compatibility and increases SDK maintenance burden for nine source repositories.

---

## References

- [CloudEvents Specification v1.0](https://cloudevents.io/specification/)
- [AWS SQS Developer Guide](https://docs.aws.amazon.com/sqs/)
- [CloudEvents SDK for Python](https://github.com/cloudevents/sdk-python)
- ADR 0001: Multi-Cloud SOC Architecture
- ADR 0002: MITRE ATT&CK RAG Corpus
