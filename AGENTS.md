# Agent Instructions

This project is **Neuro-Symbolic Software Security (NSSS)**, a hybrid static analysis system combining classic techniques (CFG, SSA) with AI/LLM insights.
As an agent, act as a **Senior Software Engineer**: proactive, rigorous, and systematic.

## 🛠️ Development Workflow

### Issue Tracking (Beads)
Use **bd** (beads) to track work. Maintain accurate state.
- `bd ready`: Find work (prioritize P0/P1).
- `bd update <id> --status in_progress`: Claim work.
- `bd close <id>`: Complete work.
- `bd sync`: Sync with git.

### Session Completion (Landing the Plane)
Work is NOT complete until `git push` succeeds.
1. **File issues** for remaining work/tech debt.
2. **Run quality gates** (`make lint`, `make test`).
3. **Update issue status**.
4. **PUSH**: `git pull --rebase` -> `bd sync` -> `git push`. Verify "up to date".

## 🏗️ Build & Verify

### Environment
- **Python**: 3.10+
- **Deps**: `requirements.txt`.
- **Virtual Env**: `make venv` (Recommended).

### Core Commands
Use `make` (or `python -m ...` equivalents) for operations.

| Task | Command | Description |
|------|---------|-------------|
| **Install** | `make install` | `pip install -r requirements.txt` |
| **Lint** | `make lint` | `ruff check .` (Strict) |
| **Format** | `make format` | `ruff format .` (Apply fixes) |
| **Test** | `make test` | `pytest` (All tests) |
| **Scan** | `make scan-fast` | Run security scan (CI mode) |
| **Clean** | `make clean` | Remove artifacts/cache |

### 🧪 Running Specific Tests
Do not run the full suite repeatedly. Focus on relevant tests.
```bash
# Run specific file
pytest tests/core/parser/test_python_ast.py

# Run specific case (substring match)
pytest -k "test_alias_resolution"

# Run failed tests from last run
pytest --lf
```

### 📜 Useful Scripts
- `scripts/evaluate_model.py`: Run model evaluation harness.
- `scripts/test_inference_api.py`: Test inference API endpoint.
- `scripts/train_model.py`: Local training script.

## 📝 Code Style & Guidelines

### 1. Formatting & Linting
- **Tooling**: `ruff`.
- **Rule**: If `make lint` passes, style is acceptable.
- **Action**: Run `make format` before committing.

### 2. Imports
- **Absolute Imports**: Start from `src`.
  - ✅ `from src.core.parser import PythonAstParser`
  - ❌ `from ..parser import PythonAstParser`
- **Group**: 1. Stdlib, 2. Third-party, 3. Local (`src...`).

### 3. Typing & Schemas
- **Strong Typing**: All signatures MUST have type hints (`List`, `Dict`, `Optional`, `Any`).
- **Pydantic**: Use for data objects/IR. Validate at boundaries.

### 4. Naming Conventions
- **Classes**: `PascalCase` (`AnalysisOrchestrator`).
- **Functions/Vars**: `snake_case` (`analyze_code`, `node_id`).
- **Constants**: `UPPER_CASE` (`MAX_DEPTH`).
- **Private**: Prefix `_` (`_visit_node`).

### 5. Error Handling & Logging
- **No Silent Failures**: No bare `except: pass`.
- **Logging**: Use centralized logger.
  ```python
  from src.core.telemetry import get_logger
  logger = get_logger(__name__)
  logger.error(f"Error: {e}")
  ```

### 6. Testing Strategy
- **Unit Tests**: Isolate logic. Mock LLM calls.
- **Fixtures**: Use `conftest.py`.
- **Coverage**: New features need tests. Regressions need reproduction cases.

## 📂 Repository Architecture

- **`src/core/parser`**: Source -> IR (AST/Graph). `python_ast.py`.
- **`src/core/cfg`**: Control/Data Flow. `builder.py`, `ssa/transformer.py`.
- **`src/core/ai`**: LLM Interface. `client.py`, `prompts.py`.
- **`src/core/scan`**: Security tools. `semgrep.py`.
- **`docs/`**: `07_IR_Schema.md` (IR Truth), `02_Ban_Do_Lo_Hong_Python.md` (Vulns).

## 🤖 Agent Behavior Rules

1. **Context First**: Read related files before editing. Understand the "Physics".
2. **Minimal Changes**: Don't refactor unrelated code.
3. **Commit Messages**: Conventional (`feat`, `fix`, `refactor`, `test`).
4. **Safety**: No API keys. Verify `git diff`.

## Learned Skills

### Skill: Implement AST Analysis Pass
- **Definition**: `.opencode/skills/implement-ast-analysis-pass/SKILL.md`
- **Usage**: Follow for new static analysis features.
- **Reference**: `src/core/parser/alias_resolver.py`.
