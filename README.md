# AI Agent Security Operations Center

[![CI](https://github.com/kogunlowo123/ai-agent-security-operations-center/actions/workflows/ci.yml/badge.svg)](https://github.com/kogunlowo123/ai-agent-security-operations-center/actions/workflows/ci.yml)
[![Security Scan](https://github.com/kogunlowo123/ai-agent-security-operations-center/actions/workflows/security.yml/badge.svg)](https://github.com/kogunlowo123/ai-agent-security-operations-center/actions/workflows/security.yml)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

An enterprise-grade AI platform that aggregates security signals from upstream AI agent systems, performs AI-powered threat triage and hunting, manages incident lifecycles, and operates a fully automated Security Operations Center (SOC) for AI agent ecosystems.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    9 Upstream AI Agent Repos                     │
│  identity │ policy │ supply-chain │ gateway │ runtime │ mesh    │
│  privacy │ sdlc │ cost-governance                                │
└─────────────────────┬───────────────────────────────────────────┘
                      │ CloudEvents (POST /api/v1/events/ingest)
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                    AI Agent SOC Platform                         │
│                                                                  │
│  ┌──────────┐  ┌───────────────┐  ┌──────────────────────────┐  │
│  │   API    │  │  Agent Runtime │  │       RAG Core           │  │
│  │ (FastAPI)│  │  (LangGraph)   │  │  (MITRE ATT&CK + Intel) │  │
│  └──────────┘  └───────────────┘  └──────────────────────────┘  │
│                                                                  │
│  ┌──────────┐  ┌───────────────┐  ┌──────────────────────────┐  │
│  │  OpenSearch │  │  PostgreSQL   │  │   Platform Gateway     │  │
│  │  (SIEM)  │  │  (pgvector)   │  │   (LiteLLM + Bedrock)   │  │
│  └──────────┘  └───────────────┘  └──────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## AI Agents

| Agent | Tier | Responsibility |
|-------|------|----------------|
| `soc-analyst` | T1 | Alert triage, MITRE ATT&CK correlation, incident creation |
| `threat-hunter` | T1 | Proactive hunting using SIEM queries and ATT&CK framework |
| `incident-responder` | T2 | Incident lifecycle management, remediation coordination |

## API Endpoints

```
POST /api/v1/events/ingest        Ingest CloudEvent from upstream repos
GET  /api/v1/incidents/{id}       Get incident record
GET  /api/v1/incidents            List active incidents
POST /api/v1/hunt/launch          Launch threat hunt job
GET  /api/v1/posture/score        Get org-wide security posture score
GET  /api/v1/health               Liveness probe
GET  /api/v1/readiness            Readiness probe
```

## Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) package manager
- Docker & Docker Compose
- AWS credentials configured

### Local Development

```bash
# Clone the repository
git clone https://github.com/kogunlowo123/ai-agent-security-operations-center.git
cd ai-agent-security-operations-center

# Copy environment configuration
cp .env.example .env
# Edit .env with your credentials

# Start all services
docker compose up -d

# Or run the API service directly
cd services/api
uv sync
uv run uvicorn src.api.main:app --reload --port 8000
```

### Running Tests

```bash
make test
# or
cd services/api && uv run pytest tests/ -v --cov=src
```

## Infrastructure

Multi-cloud deployment across:

- **AWS (Primary)**: EKS, Aurora PostgreSQL (pgvector), OpenSearch, SQS, S3, Bedrock
- **Azure (Secondary)**: AKS, Azure Container Registry
- **GCP (Tertiary)**: GKE, Vertex AI

### Terraform Deployment

```bash
# AWS
cd infra/envs/aws/prod
terraform init
terraform plan -out=tfplan
terraform apply tfplan

# Azure
cd infra/envs/azure/prod
terraform init && terraform apply

# GCP
cd infra/envs/gcp/prod
terraform init && terraform apply
```

## Security

- All container images must be signed (Kyverno policy enforced)
- OPA policies for fine-grained access control
- STRIDE threat model documented in `security/threat-models/`
- SIEM integration with OpenSearch for all security events
- UEBA baselines for AI agent behavioral analytics
- SOAR playbooks for automated response

## Event Sources

The platform ingests CloudEvents from these upstream repositories:

1. `ai-agent-identity-governance` → `identity.access.violation`
2. `ai-agent-policy-enforcement-runtime` → `policy.enforcement.breach`
3. `ai-agent-supply-chain-security` → `supply_chain.integrity.failure`
4. `ai-agent-api-gateway-security` → `gateway.abuse.detected`
5. `ai-agent-runtime-guardrails` → `runtime.guardrail.triggered`
6. `ai-agent-multi-cloud-mesh` → `mesh.anomaly.detected`
7. `ai-agent-data-privacy-compliance` → `privacy.violation.detected`
8. `ai-agent-sdlc-code-security` → `sdlc.vulnerability.found`
9. `ai-agent-cost-governance` → `cost.anomaly.detected`

## Posture Scoring

Security posture is computed as a weighted aggregate across all signal sources:

| Component | Weight |
|-----------|--------|
| Identity | 20% |
| Policy | 20% |
| Runtime | 20% |
| Supply Chain | 15% |
| SDLC | 15% |
| Mesh | 10% |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines.

## Security Policy

See [SECURITY.md](SECURITY.md) for vulnerability reporting instructions.

## License

Apache License 2.0 — see [LICENSE](LICENSE) for details.
