# Contributing to LLMOps

Thank you for your interest in contributing! This document outlines the process for contributing to LLMOps and helps you get started quickly.

## Table of Contents

- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Code Standards](#code-standards)
- [Testing Guidelines](#testing-guidelines)
- [Pull Request Process](#pull-request-process)
- [Review Process](#review-process)
- [Architecture Guidelines](#architecture-guidelines)
- [Documentation Standards](#documentation-standards)
- [Questions and Support](#questions-and-support)

---

## Getting Started

1. **Fork** the repository on GitHub
2. **Clone** your fork locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/llmops.git
   cd llmops
   ```
3. **Add the upstream remote:**
   ```bash
   git remote add upstream https://github.com/gokulnathan66/llmops.git
   ```
4. **Create a branch** for your work (see [branch naming](#branch-naming)):
   ```bash
   git checkout -b feat/your-feature-name
   ```

---

## Development Setup

### Prerequisites

- Python 3.13+
- [uv](https://github.com/astral-sh/uv) package manager
- Docker & Docker Compose (for local Qdrant)
- AWS credentials with Bedrock access (`ap-south-1` or your region)
- Terraform 1.6+ (for infrastructure changes)

### Installation

```bash
# Install dependencies
uv sync

# Copy and configure environment
cp .env.example .env
# Edit .env with your credentials

# Start local Qdrant
docker compose up -d

# Verify the API starts
uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
curl http://localhost:8000/health
```

### Environment Variables

Copy `.env.example` to `.env` and fill in the required values. See the [Configuration Reference](README.md#configuration-reference) for full documentation.

---

## Code Standards

### Style Guide

This project uses [Ruff](https://docs.astral.sh/ruff/) for linting and formatting. All code must pass the configured rules before merging.

```bash
# Format code
uv run ruff format .

# Lint and auto-fix
uv run ruff check . --fix

# Type checking
uv run mypy src/
```

### Naming Conventions

| Scope | Convention | Example |
|-------|-----------|---------|
| Functions/variables | `snake_case` | `embed_query`, `session_id` |
| Classes | `PascalCase` | `EmbeddingService`, `QdrantService` |
| Constants | `UPPER_SNAKE_CASE` | `RAG_THRESHOLD`, `MAX_TOKENS` |
| Files/modules | `snake_case` | `rag_evaluator.py`, `bedrock.py` |
| Terraform resources | `snake_case` | `aws_dynamodb_table.conversations` |

### General Rules

- Keep functions focused — one responsibility per function
- Prefer explicit over implicit
- Type-annotate all function signatures
- No bare `except:` — always catch specific exceptions
- Use `from __future__ import annotations` in all new modules
- Default to writing no comments; only add when the WHY is non-obvious

---

## Testing Guidelines

### Running Tests

```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/lambdas/test_rag_evaluator.py -v

# Run with coverage
uv run pytest --cov=src --cov=evaluations --cov-report=term-missing
```

### Writing Tests

- Place tests under `tests/` mirroring the source structure
- Use `unittest.mock.patch` to mock AWS services; use `moto` for DynamoDB integration tests
- Do **not** mock the DynamoDB table schema — use `moto` with the real table definition
- Every new module needs at least:
  - Unit tests for pure functions
  - Integration tests for AWS service interactions (via moto)

### Test Structure

```python
# tests/lambdas/test_my_module.py
import pytest
from unittest.mock import patch, MagicMock
from evaluations.my_module import my_function

def test_my_function_happy_path():
    result = my_function(valid_input)
    assert result["key"] == expected_value

@patch("evaluations.my_module.BedrockService")
def test_my_function_with_bedrock(mock_bedrock_cls):
    mock_bedrock = MagicMock()
    mock_bedrock_cls.return_value = mock_bedrock
    mock_bedrock.converse_text.return_value = "mocked response"
    ...
```

---

## Pull Request Process

### Branch Naming

```
feat/short-description       # New features
fix/short-description        # Bug fixes
docs/short-description       # Documentation only
refactor/short-description   # Code refactoring
test/short-description       # Test additions/updates
chore/short-description      # Build, CI, or tooling changes
infra/short-description      # Terraform / infrastructure changes
```

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <short summary>

[optional body]

[optional footer]
```

**Types:** `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `infra`

**Examples:**
```
feat(eval): add HITL flagging threshold to PCA runner
fix(bedrock): use tool-use instead of outputConfig for structured output
docs(readme): update quick start with ap-south-1 region note
infra(dynamo): add eval_type GSI to evaluations table
```

### PR Checklist

Before opening a PR, ensure:

- [ ] All tests pass (`uv run pytest`)
- [ ] Code is formatted (`uv run ruff format .`)
- [ ] No linting errors (`uv run ruff check .`)
- [ ] New functionality is covered by tests
- [ ] Documentation updated if behavior changed
- [ ] No secrets or credentials in the diff
- [ ] `CHANGELOG.md` updated under `[Unreleased]`

### PR Size

Keep PRs focused. Prefer multiple small PRs over one large one. A good PR changes fewer than 400 lines of non-test code.

---

## Review Process

Reviewers look for:

1. **Correctness** — does the code do what it claims?
2. **Tests** — are edge cases covered? do mocks reflect real AWS behavior?
3. **Security** — no hardcoded credentials, no SQL/command injection vectors
4. **Performance** — no unnecessary Bedrock/Qdrant calls in hot paths
5. **Consistency** — follows existing patterns in the codebase

PRs require **1 approving review** before merge. The author should respond to all comments before requesting re-review.

---

## Architecture Guidelines

### Adding a New Evaluation

1. Create `evaluations/my_eval.py` with a `handler(event, context)` entry point
2. Add corresponding `tests/lambdas/test_my_eval.py`
3. If it needs a new DynamoDB table, add it to `iac/terraform-aws/data_managment/dynamodb.tf`
4. Register an EventBridge schedule in `iac/terraform-aws/evaluations/eventbridge.tf`
5. Add a Lambda resource in `iac/terraform-aws/evaluations/lambda.tf`

### Adding a New LangGraph Node

1. Create `src/nodes/my_node.py`
2. Decorate the node function with `@observe()` for Langfuse tracing
3. Add a fallback for any Langfuse prompt renders
4. Wire it into `src/graph/builder.py`
5. Update `src/states/config.py` if new state fields are required

### Service Layer Rules

- AWS clients are instantiated inside `__init__` — never as module-level globals
- All Bedrock calls go through `BedrockService` — never call the boto3 client directly from nodes
- Structured output always uses tool-use (`toolConfig`) — never `outputConfig`

---

## Documentation Standards

- Keep the top-level `README.md` as the entry point
- Use `docs/` for deeper reference material
- Code comments: only when the WHY is non-obvious
- Update `CHANGELOG.md` for every user-visible change

---

## Questions and Support

- **GitHub Discussions** — for questions, ideas, and general conversation
- **GitHub Issues** — for bug reports and concrete feature requests
- **Security issues** — see [SECURITY.md](SECURITY.md) — do not open public issues

Please search existing issues and discussions before opening a new one.
