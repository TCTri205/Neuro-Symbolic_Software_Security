# Agent Instructions

This project is **Neuro-Symbolic Software Security (NSSS)**, a hybrid static analysis system combining classic techniques (CFG, SSA) with AI/LLM insights.
As an agent working here, you are expected to act as a **Senior Software Engineer**: proactive, rigorous, and systematic.

## 🛠️ Development Workflow

### Issue Tracking (Beads)
This project uses **bd** (beads) for issue tracking. You must maintain the state of your work accurately.

**Quick Reference:**
```bash
bd ready              # Find available work (prioritize P0/P1)
bd show <id>          # View issue details
bd update <id> --status in_progress  # Claim work (ONLY one at a time)
bd close <id>         # Complete work
bd sync               # Sync with git
```

### Session Completion (Landing the Plane)
**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

1. **File issues** for remaining work or technical debt discovered.
2. **Run quality gates** (Lint + Test).
3. **Update issue status** (Close finished work, update in-progress items).
4. **PUSH TO REMOTE** (Mandatory):
   ```bash
   git pull --rebase
   bd sync
   git push
   # Verify:
   git status  # MUST show "up to date with origin"
   ```

---

## 🏗️ Build & Verify

### Environment
- **Python**: 3.10+
- **Dependencies**: Managed via `requirements.txt`.
- **Virtual Env**: Recommended (`make venv`).

### Core Commands
Use `make` for standardized operations.

| Task | Command | Description |
|------|---------|-------------|
| **Install** | `make install` | Install dependencies |
| **Lint** | `make lint` | Run Ruff linter (Strict) |
| **Format** | `make format` | Run Ruff formatter (Apply fixes) |
| **Test (All)** | `make test` | Run all tests with coverage |
| **Scan (Fast)** | `make scan-fast` | Run security scan (CI mode) |
| **Clean** | `make clean` | Remove artifacts and cache |

### Running Specific Tests (Crucial for Agents)
Do not run the full suite repeatedly. Focus on the relevant tests.

```bash
# Run a specific test file
pytest tests/core/parser/test_python_ast.py

# Run a specific test case by name (substring match)
pytest -k "test_alias_resolution"

# Run with verbose output to see assertion details
pytest -vv tests/core/parser/test_python_ast.py

# Run failed tests from the last run (quick iteration)
pytest --lf
```

---

## 📝 Code Style & Guidelines

### 1. Formatting & Linting
- **Tooling**: We use `ruff` for everything.
- **Rule**: If `make lint` passes, the style is acceptable.
- **Action**: Always run `make format` before committing to auto-fix styling issues.

### 2. Imports
- **Absolute Imports**: Use absolute imports starting from `src`.
  - ✅ `from src.core.parser import PythonAstParser`
  - ❌ `from ..parser import PythonAstParser`
- **Organization**:
  1. Standard Library (`import os`, `import typing`)
  2. Third-party (`import pydantic`, `import networkx`)
  3. Local Application (`from src.core...`)

### 3. Typing & Schemas
- **Strong Typing**: All function signatures must have type hints.
  - Use `typing.List`, `typing.Dict`, `typing.Optional`, `typing.Any`.
  - Use modern union syntax `type | None` if Python version permits (3.10+).
- **Pydantic**: Use Pydantic models for data objects, especially for the IR (Intermediate Representation).
  - validate data at boundaries using `model_validate`.

### 4. Naming Conventions
- **Classes**: `PascalCase` (e.g., `AnalysisOrchestrator`, `IRGraph`).
- **Functions/Methods**: `snake_case` (e.g., `analyze_code`, `_build_cfg`).
- **Variables**: `snake_case` (e.g., `source_lines`, `node_id`).
- **Constants**: `UPPER_CASE` (e.g., `MAX_RECURSION_DEPTH`).
- **Private Members**: Prefix with `_` (e.g., `_visit_node`).

### 5. Error Handling & Logging
- **No Silent Failures**: Never use bare `except: pass`.
- **Logging**: Use the project's centralized logger.
  ```python
  from src.core.telemetry import get_logger
  logger = get_logger(__name__)
  
  # ...
  logger.error(f"Failed to parse file {file_path}: {e}")
  ```
- **Resilience**: The pipeline processes many files. A failure in one file should log an error and continue to the next, adding the error to `AnalysisResult.errors`.

### 6. Testing Strategy
- **Unit Tests**: Isolate logic. Mock LLM calls (`src.core.ai.client.LLMClient`) to avoid costs and latency during tests.
- **Fixtures**: Use `conftest.py` fixtures for complex object creation (e.g., a pre-populated `IRGraph`).
- **Coverage**: New features must have tests. Regressions must be fixed with a reproduction test case.

---

## 📂 Repository Architecture

- **`src/core/parser`**: The brain. Converts source code -> IR (AST/Graph).
  - *Key File*: `python_ast.py` (Main logic), `ir.py` (Schema).
- **`src/core/cfg`**: Control Flow and Data Flow.
  - *Key File*: `builder.py` (CFG construction), `ssa/transformer.py` (SSA).
- **`src/core/ai`**: Interface with LLMs.
  - *Key File*: `client.py` (API wrapper), `prompts.py` (Prompt Engineering).
- **`src/core/scan`**: Traditional security scanning tools.
  - *Key File*: `semgrep.py`, `secrets.py`.

## 🤖 Agent Behavior Rules

1. **Context First**: Before editing, read related files to understand the "Physics" of the codebase (how things connect).
2. **Minimal Changes**: Do not refactor unrelated code unless necessary.
3. **Commit Messages**: Use Conventional Commits.
   - `feat(...)`: New features
   - `fix(...)`: Bug fixes
   - `refactor(...)`: Code restructuring without behavior change
   - `test(...)`: Adding/Updating tests
4. **Safety**:
   - Never commit API keys.
   - Never run destructive commands without verification.
   - Verify `git diff` before committing.

## 🔎 Reference Documentation
- `docs/07_IR_Schema.md`: The Source of Truth for the Intermediate Representation.
- `docs/02_Ban_Do_Lo_Hong_Python.md`: The definitions of vulnerabilities we detect.

*(End of Instructions)*
