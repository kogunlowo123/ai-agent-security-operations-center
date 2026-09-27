"""
RAG Core: MITRE ATT&CK corpus ingestion, chunking, embedding, and retrieval.

This package implements the full RAG pipeline for the AI Agent Security
Operations Center, including:
  - MITRE ATT&CK corpus ingestion via STIX2 and mitreattack-python
  - Hierarchical chunking with technique/tactic boundaries
  - BGE-M3 dense embeddings + BM25 sparse indexing
  - Hybrid retrieval with Reciprocal Rank Fusion (RRF, k=60)
  - Multi-hop decomposition (max 3 hops via LiteLLM)
  - Corrective RAG quality gating
  - pgvector HNSW index + OpenSearch BM25
"""

__version__ = "0.1.0"
