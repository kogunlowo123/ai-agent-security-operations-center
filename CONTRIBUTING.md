# Contributing to AI Agent Security Operations Center

Thank you for your interest in contributing to this project. This document describes the contribution process, code standards, and workflows you should follow.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Pull Request Process](#pull-request-process)
- [Code Style](#code-style)
- [Testing](#testing)
- [Commit Messages](#commit-messages)
- [Security Issues](#security-issues)

---

## Code of Conduct

All contributors are expected to uphold respectful, professional conduct. Harassment, discrimination, and bad-faith contributions are not tolerated. By participating you agree to abide by these expectations.

---

## Getting Started

### Prerequisites

- Python 3.11+
- Docker 24+
- Docker Compose v2
- Terraform 1.7+
- `make`

### Initial Setup

```bash
# 1. Fork and clone the repository
git clone https://github.com/<your-fork>/ai-agent-security-operations-center.git
cd ai-agent-security-operations-center

# 2. Copy environment template
cp .env.example .env
# Edit .env with your local values

# 3. Install Python dependencies and pre-commit hooks
make install

# 4. Spin up local services
docker compose up -d postgres opensearch redis

# 5. Verify the stack
make test
```

---

## Development Workflow

1. **Create a feature branch** from `main`:

   ```bash
   git checkout -b feat/your-feature-name
   # or
   git checkout -b fix/issue-123-short-description
   ```

2. **Implement your changes** following the code style described below.

3. **Write tests** for new logic. Aim for ≥ 80% coverage on new code paths.

4. **Run the full quality suite** before pushing:

   ```bash
   make lint
   make test
   ```

5. **Push and open a PR** against `main`.

---

## Pull Request Process

1. **Title** must follow the Conventional Commits format:
   `feat(scope): short imperative description`
   `fix(scope): short description`
   `chore(scope): short description`

2. **Description** must include:
   - What problem this PR solves
   - How you tested it
   - Any infrastructure or dependency changes

3. **All CI checks** must pass: lint, type-check, unit tests, security scan.

4. **At least one approval** from a codeowner (`@kogunlowo123`) is required before merge.

5. Squash merges are preferred for feature branches. Merge commits are used for release branches.

6. **Do not** force-push to `main` or any shared branch.

---

## Code Style

### Python

- Formatter: **Black** (`line-length = 120`)
- Linter: **Ruff** (configured in `pyproject.toml`)
- Type checker: **mypy** (strict mode for `src/`)
- Docstrings: Google style
- All public functions and classes must have type annotations and docstrings.

```python
def analyze_alert(alert: Alert, context: AgentContext) -> AnalysisResult:
    """Analyze a security alert using the reasoning agent.

    Args:
        alert: The incoming alert to triage.
        context: Current agent execution context including memory and tools.

    Returns:
        AnalysisResult containing severity, confidence, and recommended actions.

    Raises:
        AlertParseError: If the alert payload is malformed.
    """
```

### Terraform

- Formatted with `terraform fmt`.
- All resources must have `tags` containing at minimum `Project`, `Environment`, and `ManagedBy`.
- Variables must have `description` and `type`.

### YAML / JSON

- Indent: 2 spaces.
- All YAML files must pass `yamllint -d relaxed`.

---

## Testing

### Running Tests

```bash
# All tests
make test

# Unit tests only
pytest tests/unit/ -v

# Integration tests (requires running Docker services)
pytest tests/integration/ -v

# With coverage
pytest --cov=src --cov-report=term-missing --cov-report=html
```

### Test Organization

```
tests/
  unit/          # Pure unit tests, no I/O
  integration/   # Tests against real services (Postgres, OpenSearch, Redis)
  e2e/           # End-to-end API tests
  fixtures/      # Shared pytest fixtures
  data/          # Sample alert payloads and mock events
```

### Coverage

- New code must maintain or improve the overall coverage percentage.
- Coverage is enforced at 80% in CI; the gate will fail below that threshold.

---

## Commit Messages

This project uses [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/).

Format: `<type>(<scope>): <subject>`

**Types:** `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`

**Scope examples:** `api`, `agents`, `ingest`, `infra`, `auth`, `db`, `opensearch`

**Examples:**

```
feat(agents): add MITRE ATT&CK enrichment to triage agent
fix(api): handle expired JWT tokens with 401 response
chore(deps): upgrade boto3 to 1.34.0
docs(contributing): add test coverage requirements
```

---

## Security Issues

**Do not open a public GitHub issue for security vulnerabilities.**

Please follow the process described in [SECURITY.md](SECURITY.md) to report vulnerabilities responsibly.
