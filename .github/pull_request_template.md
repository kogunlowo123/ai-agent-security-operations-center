## Description

<!-- Provide a concise summary of what this PR does and why. Link to any relevant issues. -->

Closes #<!-- issue number -->

## Type of Change

<!-- Check the boxes that apply. Delete rows that are not applicable. -->

- [ ] Bug fix (non-breaking change that fixes an issue)
- [ ] New feature (non-breaking change that adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] New agent capability or integration
- [ ] Security fix or hardening
- [ ] Infrastructure / IaC change
- [ ] Documentation update
- [ ] Dependency update

## Changes Made

<!-- List the key changes made in this PR. Use bullet points for clarity. -->

- 
- 
- 

## Testing

<!-- Describe the tests you ran to verify your changes. -->

### Test Coverage

- [ ] Unit tests added/updated for new code paths
- [ ] Integration tests added/updated
- [ ] End-to-end tests added/updated (if applicable)
- [ ] Manual testing performed — describe below

### Manual Testing Steps

```
# Describe the steps you followed to manually test:
1.
2.
3.
```

### Test Results

```
# Paste relevant test output or coverage report snippet:
```

## Security Review

<!-- Security is a first-class concern in this project. Please complete all items. -->

- [ ] No secrets, API keys, or credentials are hardcoded or committed
- [ ] New dependencies have been reviewed for known CVEs (`pip-audit` or `trivy`)
- [ ] Input validation and sanitization is implemented for any new user-facing interfaces
- [ ] Authentication/authorization is enforced for new API endpoints or agent actions
- [ ] Least-privilege principle is applied to any new IAM roles, service accounts, or permissions
- [ ] No new attack surface is introduced without explicit threat model review
- [ ] Logging does not emit PII, secrets, or sensitive security data
- [ ] New agent prompts have been reviewed for prompt injection vulnerabilities

## Documentation

- [ ] Inline code comments are updated/added for complex logic
- [ ] `README.md` updated (if user-facing changes)
- [ ] Architecture documentation updated (if architectural changes)
- [ ] `CHANGELOG.md` updated
- [ ] API docs / OpenAPI spec updated (if applicable)
- [ ] Runbook / SOC playbook updated (if agent behavior or alerting changes)

## Infrastructure / IaC Changes

<!-- Complete this section only if infrastructure files (infra/**) were modified. -->

- [ ] Terraform plan reviewed and pasted below (or linked as workflow artifact)
- [ ] No unintended resource deletions in plan output
- [ ] New resources are tagged correctly (`project`, `env`, `managed-by`)
- [ ] Cost impact assessed (new resources or scaling changes)

<details>
<summary>Terraform Plan Summary</summary>

```
Paste terraform plan output here (or "N/A")
```

</details>

## Agent-Specific Checklist

<!-- Complete this section only for changes to agent logic, prompts, or tools. -->

- [ ] Agent system prompt changes reviewed for safety and alignment
- [ ] Tool/function definitions are well-typed and validated
- [ ] Rate limiting and retry logic is in place for external API calls
- [ ] Agent state management is idempotent where required
- [ ] Adversarial input testing performed (prompt injection, tool misuse)
- [ ] Human-in-the-loop checkpoints preserved for high-risk actions

## Rollback Plan

<!-- Describe how to roll back this change if it causes issues in production. -->

1. 
2. 

## Reviewer Notes

<!-- Anything specific you want reviewers to focus on? -->

---

**Reminder:** This repository contains security-sensitive agent code. All PRs require at least one security-aware review before merge.
