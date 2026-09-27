# Security Policy

## Supported Versions

The following versions currently receive security updates:

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | Yes                |

Older versions are not backported. Please upgrade to the latest release to receive security fixes.

---

## Reporting a Vulnerability

**Please do NOT report security vulnerabilities through public GitHub issues, pull requests, or discussions.**

### Private Disclosure Process

1. **Email:** Send a detailed report to `security@example.com` (replace with your actual address).
2. **Subject line:** `[SECURITY] AI Agent SOC — <brief description>`
3. **PGP encryption:** If you have a sensitive payload, use the public key available at `https://example.com/.well-known/security.txt`.

### What to Include

To help us triage and reproduce the issue quickly, please include:

- A clear description of the vulnerability and its impact.
- The affected component (API, agent runtime, ingest pipeline, infrastructure, etc.).
- Step-by-step reproduction instructions or a proof-of-concept.
- The version or commit hash where you observed the issue.
- Any suggested mitigations you are aware of.
- Your preferred disclosure timeline (we aim for 90 days maximum).

### Response Timeline

| Step | Target SLA |
| ---- | ---------- |
| Acknowledgement | 48 hours |
| Initial severity assessment | 5 business days |
| Patch available (critical) | 14 days |
| Patch available (high) | 30 days |
| Patch available (medium/low) | 90 days |
| Public disclosure | Coordinated with reporter |

We follow responsible disclosure and will credit researchers who report valid vulnerabilities, unless they prefer to remain anonymous.

---

## Security Architecture Principles

This project handles sensitive security telemetry and AI agent orchestration. The following controls are in place:

### Authentication & Authorization

- All API endpoints are protected with JWT (RS256) tokens.
- Role-based access control (RBAC) enforces least-privilege for agents and users.
- Service-to-service calls use short-lived signed tokens, never long-lived shared secrets.

### Secrets Management

- No secrets are committed to source control.
- All runtime secrets are injected via environment variables or fetched from AWS Secrets Manager / HashiCorp Vault.
- The `.env.example` file contains only placeholder values.

### Data Protection

- Security event data at rest is encrypted (AES-256 for Postgres, OpenSearch).
- Data in transit is protected with TLS 1.2+ for all service communication.
- PII in logs is redacted before storage.

### AI Agent Safety

- Agent tool calls are restricted to a declared capability manifest; no arbitrary code execution.
- All agent-generated actions that modify external systems require a human-in-the-loop approval step at severity ≥ HIGH.
- Prompt injection mitigations are applied at all ingestion boundaries.

### Supply Chain

- Dependencies are pinned to exact versions in `requirements*.txt` and Terraform lock files.
- All container images are scanned for CVEs in CI using Trivy before push.
- SBOM is generated on every release build.

---

## Known Limitations

- This is a pre-release (0.1.x) project. The attack surface has not been subjected to a formal third-party penetration test.
- Automated response actions are disabled by default and must be explicitly enabled by an administrator.
