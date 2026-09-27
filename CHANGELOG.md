# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added

- _Nothing yet._

---

## [0.1.0] - 2024-12-01

### Added

- Initial project scaffold with multi-service Docker Compose stack.
- `services/api` — FastAPI-based REST and WebSocket gateway for alert ingestion, triage queries, and agent status.
- `services/agents` — AI agent runtime built on LangGraph; includes Triage Agent, Correlation Agent, and Remediation Proposal Agent.
- `services/ingest` — Event ingest pipeline: normalizes raw security events (CloudTrail, GuardDuty, Syslog, OCSF) into a canonical alert schema.
- `infra/terraform` — Terraform modules for AWS (Bedrock, RDS, OpenSearch Service, ECS Fargate, IAM).
- OpenSearch integration for SIEM-style alerting, index templates, and ILM policies.
- Postgres with `pgvector` extension for embedding-based alert deduplication and similarity search.
- OpenTelemetry tracing and metrics exported via OTLP to a collector sidecar.
- JWT RS256 authentication with role-based access control (`analyst`, `senior_analyst`, `admin`).
- MITRE ATT&CK enrichment: maps alert indicators to tactics, techniques, and sub-techniques.
- Makefile targets: `install`, `test`, `lint`, `format`, `docker-build`, `docker-push`, `terraform-init`, `terraform-plan`, `terraform-apply`, `dev`, `clean`.
- Pre-commit hooks: Black, Ruff, mypy, trailing-whitespace, YAML/JSON validation, Hadolint, commitizen.
- CODEOWNERS, CONTRIBUTING.md, SECURITY.md, and `.env.example`.

### Security

- All secrets injected via environment variables; `.env.example` ships with placeholder values only.
- Agent tool calls scoped to a declared capability manifest; no arbitrary execution.
- Human-in-the-loop gate for automated remediation actions at severity ≥ HIGH.

---

[Unreleased]: https://github.com/kogunlowo123/ai-agent-security-operations-center/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/kogunlowo123/ai-agent-security-operations-center/releases/tag/v0.1.0
