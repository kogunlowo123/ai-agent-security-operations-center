# ADR 0002: RAG over MITRE ATT&CK Corpus Instead of Fine-Tuning

**Status:** Accepted  
**Date:** 2024-11-22  
**Deciders:** AI/ML Engineering, Security Architecture, Platform Engineering  
**Supersedes:** N/A  
**Superseded by:** N/A

---

## Context

The AI triage and threat hunt agents need deep knowledge of the MITRE ATT&CK framework (Enterprise, Mobile, ICS matrices — ~770 techniques, ~400 sub-techniques as of ATT&CK v15) to:

1. **Classify events** against ATT&CK techniques (e.g. "Pass-the-Hash" → T1550.002).
2. **Generate hunt hypotheses** grounded in known adversary behaviour patterns.
3. **Explain detections** to analysts with references to ATT&CK procedural examples.
4. **Suggest mitigations** that map to ATT&CK mitigations (M1026, M1032, etc.).

ATT&CK evolves: MITRE releases major updates roughly twice a year. Techniques are added, renamed, deprecated, or re-numbered. Our threat landscape tracking also includes custom threat intel (ISAC reports, internal incident post-mortems).

We evaluated two primary approaches for incorporating ATT&CK knowledge:

| Option | Description |
|---|---|
| A | **Fine-tune** a foundation model on ATT&CK corpus + internal threat intel |
| B | **RAG** (Retrieval-Augmented Generation) over a vector index of ATT&CK techniques |
| C | **Hybrid**: fine-tune for classification + RAG for generation |

## Decision

Adopt **RAG over a versioned MITRE ATT&CK corpus** as the knowledge backbone for the AI agents. Fine-tuning is deferred pending evidence that RAG cannot meet accuracy thresholds.

The RAG corpus includes:
1. **MITRE ATT&CK STIX 2.1 corpus** (all Enterprise, Mobile, ICS techniques) — loaded from `attack-stix-data` GitHub releases.
2. **ATT&CK Navigator layers** for the threat groups relevant to our sector (financial services).
3. **Internal threat intel reports** (post-incident reports, ISAC bulletins, red team findings) — ingested via the platform's document ingestion pipeline.
4. **NIST SP 800-53 Rev 5 control catalogue** for mitigation mapping.

Retrieval pipeline:
- Embedding model: `text-embedding-3-large` (3072-dim) via the Claude API batch embedding endpoint.
- Vector store: Amazon OpenSearch k-NN (HNSW, ef=512, m=48) for low-latency ANN search.
- Chunking: ATT&CK techniques are stored as individual documents with metadata (technique_id, tactic, platforms, data_sources, mitigations). Procedural examples are chunked at 400 tokens with 50-token overlap.
- Reranking: cross-encoder reranker (ms-marco-MiniLM-L-12-v2) applied to top-20 candidates to produce final top-5.

## Consequences

### Why RAG beats fine-tuning here

**Currency**: ATT&CK v14 → v15 introduced 12 new techniques and deprecated 3. A RAG corpus can be updated by re-indexing new STIX bundles. A fine-tuned model requires retraining ($8,000–$40,000 per run for a 7B–70B model) and a multi-week evaluation cycle. Freshness SLA for the corpus: ≤7 days after a new ATT&CK release.

**Attribution / explainability**: RAG returns cited source passages. An analyst can see exactly which ATT&CK technique description, procedural example, or threat group report drove a classification decision. Fine-tuned models cannot provide this — a requirement for our SOC 2 audit trail.

**Accuracy on long-tail techniques**: ATT&CK has many rare sub-techniques (used by <5 known threat groups). RAG can retrieve the exact technique document; a fine-tuned model may have learned only statistical associations from sparse training examples.

**Cost at scale**: RAG adds ~40–80 ms latency per agent turn (embedding + ANN search + rerank). This is within our 500 ms agent step SLA. Fine-tuned model hosting costs $12,000–$30,000/month for dedicated GPU instances.

### Positive
- ATT&CK knowledge stays current within days of a MITRE release without model retraining.
- Every agent answer includes ATT&CK technique citations (links to attack.mitre.org).
- Internal threat intel is searchable alongside ATT&CK — no separate knowledge base.
- Eval framework can score citation accuracy and faithfulness (see `evals/generation/`).
- Corpus updates are auditable: every indexing run is logged with source version and timestamp.

### Negative / Risks
- **Retrieval failure** on novel or never-seen-before attack patterns not yet in ATT&CK.
  - Mitigated by: hybrid retrieval with BM25 keyword search as a fallback; agents are instructed to flag "possible novel technique — not in ATT&CK corpus" when confidence is low.
- **Context window pressure**: top-5 technique passages (~2,000 tokens) plus event data may crowd out reasoning space.
  - Mitigated by: concise chunking; the reranker keeps only the most relevant 800 tokens per passage.
- **Hallucination risk** if the model generates ATT&CK technique IDs not present in retrieved context.
  - Mitigated by: `citation_accuracy` eval gate in CI (threshold 0.85); retrieval grounding instructions in system prompt.
- **Index drift** if the corpus indexing pipeline fails silently.
  - Mitigated by: daily staleness check — alert if ATT&CK index last-updated timestamp > 14 days old.

### Neutral
- The fine-tuning option remains viable if Recall@10 < 0.75 after 90 days of production operation. This ADR will be revisited at that point.
- The cross-encoder reranker adds 30–50 ms per turn. If latency SLAs tighten, the reranker may be removed and replaced with a trained bi-encoder.

## Corpus Versioning

Each ATT&CK index build is tagged with `corpus_version` (e.g. `attck-v15.0-20241101`). Agent responses include this tag in their metadata so analysts know which version of ATT&CK drove the classification.

## Review Date

This ADR is subject to review when:
- Recall@10 drops below 0.75 in the nightly CI eval gate, OR
- A new ATT&CK major version introduces breaking changes to the STIX schema, OR
- Model context windows expand to >200K tokens (making fine-tuning cost-effective).

Next scheduled review: 2025-05-01.
