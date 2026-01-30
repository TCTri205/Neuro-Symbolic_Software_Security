# NSSS Final System Architecture

**Version:** 2.3 Final  
**Date:** January 30, 2026  
**Architecture Philosophy:** Engineering First, AI Second

---

## Table of Contents
1. [System Overview](#system-overview)
2. [Layer Architecture](#layer-architecture)
3. [Data Flow](#data-flow)
4. [Component Details](#component-details)
5. [Deployment Topologies](#deployment-topologies)
6. [Extension Points](#extension-points)

---

## System Overview

NSSS is a hybrid static application security testing (SAST) system that combines:

1. **Classic Program Analysis** (CFG, SSA, Taint Tracking)
2. **AI/LLM Semantic Verification** (OpenAI, Gemini, Local models)
3. **Multi-Tool Orchestration** (Semgrep, CVE databases, Secret scanners)

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        USER INTERFACES                       │
├─────────────────────────────────────────────────────────────┤
│  CLI (nsss-scan)  │  Colab Server  │  API (Future: IDE)   │
└─────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    ANALYSIS ORCHESTRATOR                     │
│  (Event-Driven Pipeline with Plugin System)                 │
└─────────────────────────────────────────────────────────────┘
                              ▼
┌──────────────┬──────────────┬──────────────┬──────────────┐
│   PARSER     │   CFG/SSA    │   TAINT      │   AI/LLM     │
│   LAYER      │   BUILDER    │   ENGINE     │   GATEWAY    │
└──────────────┴──────────────┴──────────────┴──────────────┘
                              ▼
┌──────────────┬──────────────┬──────────────┬──────────────┐
│   SECURITY   │   LIBRARIAN  │   PRIVACY    │   REPORTING  │
│   SCANNERS   │   (CVE DB)   │   MASKING    │   ENGINE     │
└──────────────┴──────────────┴──────────────┴──────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     PERSISTENCE LAYER                        │
│  (SQLite Cache, NetworkX Graphs, Baseline Files)            │
└─────────────────────────────────────────────────────────────┘
```

---

## Layer Architecture

### 1. **Presentation Layer**

#### CLI (`src/runner/cli/main.py`)
- **Framework**: Typer + Rich
- **Commands**:
  - `nsss-scan <path>`: Main analysis entry point
  - `--format`: Output format (sarif, markdown, json, graph)
  - `--baseline`: Enable FP suppression
  - `--diff`: Incremental scanning (git-based)
  - `--remote-llm`: Connect to remote LLM server

#### Colab Server (`src/server/colab_server.py`)
- **Framework**: Flask + ngrok
- **Endpoints**:
  - `POST /analyze`: Submit code for analysis
  - `GET /health`: Server status
- **Use Case**: Zero-cost LLM inference for students/researchers

---

### 2. **Orchestration Layer**

#### Analysis Orchestrator (`src/core/pipeline/orchestrator.py`)

**Responsibilities:**
- Coordinate multi-stage analysis pipeline
- Emit lifecycle events for plugin hooks
- Handle errors and fallback strategies

**Pipeline Stages:**
```
1. IR_GENERATION       → Parse AST to IR
2. GRAPH_BUILD         → Construct CFG
3. SSA_TRANSFORM       → Apply SSA form
4. STATIC_SCAN         → Run Semgrep + Secret scanner
5. DEPENDENCY_ANALYSIS → Check CVEs via Librarian
6. TAINT_ANALYSIS      → Propagate taint sources → sinks
7. RISK_ROUTING        → Route high-risk to LLM, low-risk to rules
8. PRIVACY_MASKING     → Redact PII before LLM calls
9. LLM_ANALYSIS        → Semantic verification
10. REPORT_GENERATION  → Output SARIF/Markdown/Graph
```

#### EventBus (`src/core/pipeline/events.py`)

**Pattern**: Observer/Publisher-Subscriber  
**Use Case**: Plugin registration for external extensions

**Events:**
- `pipeline_started`
- `stage_completed(stage_name, context)`
- `finding_detected(finding)`
- `pipeline_completed`

**Plugin Example:**
```python
from src.core.pipeline.events import register_plugin

class MetricsPlugin:
    def on_pipeline_started(self, context):
        context["start_time"] = time.time()
    
    def on_pipeline_completed(self, context):
        duration = time.time() - context["start_time"]
        log_metric("analysis_duration", duration)

register_plugin(MetricsPlugin())
```

---

### 3. **Analysis Layer**

#### 3.1 Parser Subsystem (`src/core/parser/`)

**Entry Point**: `PythonAstParser`

**Transformation Pipeline:**
```
Python Source Code
     ↓
[PythonAstParser]  → Convert AST to IR (typed nodes/edges)
     ↓
[AliasResolver]    → Resolve import aliases (e.g., pd = pandas)
     ↓
[DecoratorUnroll]  → Extract decorator metadata
     ↓
[ObfuscationDetector] → Flag base64/exec/eval patterns
     ↓
[EmbeddedLangDetector] → Detect SQL/NoSQL in f-strings
     ↓
IR (Pydantic Models)
```

**IR Schema** (see `docs/07_IR_Schema.md`):
```python
@dataclass
class IRNode:
    id: str
    ast_type: str  # "Assign", "Call", "FunctionDef", etc.
    attributes: Dict[str, Any]
    source_line: int
    taint_info: Optional[TaintInfo]

@dataclass
class IREdge:
    source: str
    target: str
    edge_type: str  # "cfg", "data", "call", "synthetic"
```

**Key Features:**
- **Template Literal Detection**: Detects SQL injection in f-strings:
  ```python
  query = f"SELECT * FROM {user_input}"  # ← Flagged as SQL injection risk
  ```
- **Async/Await Handling**: Correctly models async control flow
- **Context Manager Flow**: Handles `with` statements and `__enter__/__exit__`

---

#### 3.2 CFG/SSA Subsystem (`src/core/cfg/`)

**CFG Builder** (`builder.py`)

**Control Flow Modeling:**
- **Sequential**: Straight-line code → linear edges
- **Conditional**: `if/else` → split edges with merge point
- **Loops**: `while/for` → back edges + break/continue handling
- **Exception**: `try/except` → exceptional flow edges
- **Function Calls**: Inter-procedural edges to callee entry

**Example CFG:**
```python
def authenticate(user, password):
    if check_password(password):  # ← Node 1 (Branch)
        return True               # ← Node 2 (Then)
    else:
        log_failure(user)         # ← Node 3 (Else)
        return False              # ← Node 4 (Merge)
```

**CFG Representation:**
```
Node 1 (check_password) → Node 2 (True branch)
                        → Node 3 (False branch)
Node 2 → Node 4 (Merge)
Node 3 → Node 4 (Merge)
```

**SSA Transformer** (`ssa/transformer.py`)

**Purpose**: Convert mutable variables to versioned immutable variables for precise data flow.

**Example:**
```python
# Original
x = input()       # x₀
if flag:
    x = sanitize(x)  # x₁
y = process(x)    # Which x? (x₀ or x₁?)

# SSA Form
x₀ = input()
if flag:
    x₁ = sanitize(x₀)
x₂ = φ(x₀, x₁)    # ← Phi node merges x₀ and x₁
y = process(x₂)
```

**Benefits**:
- **Precise Taint Tracking**: Know exact data flow path
- **Dead Code Detection**: Unused definitions are visible
- **Optimization**: Enables compiler-like optimizations

---

#### 3.3 Taint Analysis Subsystem (`src/core/taint/`)

**TaintEngine** (`engine.py`)

**Algorithm**: Bi-directional Taint Propagation

**Phase 1: Forward Propagation (Sources → Sinks)**
```python
# Example
user_input = request.GET["q"]    # ← SOURCE (taint₁)
cleaned = escape_html(user_input) # ← Propagate taint₁
response = render(cleaned)        # ← SINK (check taint₁)
```

**Phase 2: Backward Propagation (Sinks → Sources)**
```python
# Verify dangerous sink reached by source
execute_sql(query)  # ← Start backward from sink
    ↑
query = f"SELECT {user_id}"  # ← Trace back to source
    ↑
user_id = request.args["id"]  # ← Confirm unsanitized source
```

**Sanitization Detection** (`src/core/analysis/sanitizers.py`)

**Context-Aware Mapping:**
```python
SANITIZER_REGISTRY = {
    "HTML": ["escape", "escape_html", "bleach.clean"],
    "SQL": ["quote", "parameterize", "SQLAlchemy.text"],
    "Shell": ["shlex.quote", "pipes.quote"],
}
```

**Example:**
```python
user_input = request.GET["html"]
safe_html = escape_html(user_input)  # ← Taint removed for HTML context
response = render_template(safe_html)  # ← OK
```

**But:**
```python
user_input = request.GET["sql"]
safe_html = escape_html(user_input)  # ← Wrong sanitizer!
execute_sql(safe_html)  # ← VULN: HTML escaping doesn't sanitize SQL
```

---

#### 3.4 AI/LLM Subsystem (`src/core/ai/`)

**LLM Gateway** (`gateway.py`)

**Architecture**: Multi-Provider Abstraction Layer

```
┌─────────────────────────────────────────┐
│         LLMGatewayService               │
├─────────────────────────────────────────┤
│  • Circuit Breaker (fault tolerance)   │
│  • Cache Store (response caching)      │
│  • Prompt Guard (injection defense)   │
│  • Constrained Decoder (JSON validation)│
└─────────────────────────────────────────┘
               ▼
┌──────────┬──────────┬──────────┬──────────┐
│  OpenAI  │  Gemini  │  Ollama  │   Mock   │
│ (gpt-4)  │(gemini-  │ (local)  │ (testing)│
│          │pro)      │          │          │
└──────────┴──────────┴──────────┴──────────┘
```

**Circuit Breaker** (`circuit_breaker.py`)

**States:**
- **CLOSED**: Normal operation
- **OPEN**: Too many failures → fail fast
- **HALF_OPEN**: Test recovery → allow 1 request

**Configuration:**
```python
CircuitBreaker(
    failure_threshold=5,     # Open after 5 failures
    recovery_timeout=60.0,   # Wait 60s before retry
    half_open_max_calls=1    # Test with 1 call
)
```

**Cache Store** (`cache_store.py`)

**Storage**: SQLite database  
**Key**: `sha256(prompt + model + temperature)`

**Benefits:**
- **Speed**: Avoid redundant LLM calls (10-100x faster)
- **Cost**: Reduce API billing
- **Determinism**: Same input → same output

**Constrained Decoder** (`decoder.py`)

**Purpose**: Ensure LLM output matches JSON schema

**Example:**
```python
schema = {
    "type": "object",
    "properties": {
        "is_vulnerable": {"type": "boolean"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1}
    },
    "required": ["is_vulnerable", "confidence"]
}

decoder = ConstrainedDecoder(schema)
result = decoder.decode(llm_output)  # ← Validates + parses
```

**Prompt Guard** (`guard.py`)

**Defense**: Prevent LLM jailbreaking attempts

**Blocked Patterns:**
```python
BLOCKED_PATTERNS = [
    r"(?i)ignore previous",
    r"(?i)disregard instructions",
    r"(?i)import\s+os",
    r"(?i)__import__",
]
```

---

#### 3.5 Security Scanner Subsystem (`src/core/scan/`)

**Multi-Tool Orchestration:**

**1. Semgrep Runner** (`semgrep.py`)
- **Rules**: Uses community/custom Semgrep rules
- **Detection**: Pattern-based vulnerability detection
- **Output**: SARIF findings

**2. Secret Scanner** (`secrets.py`)
- **Regex Patterns**: AWS keys, GitHub tokens, Stripe keys
- **Entropy Detection**: High-entropy strings (Shannon entropy > 3.5)
- **False Positive Filtering**: Ignore test fixtures, placeholders

**3. Baseline Engine** (`baseline.py`)
- **Purpose**: Suppress known false positives
- **Storage**: `.nsss_baseline.json`
- **Format**:
  ```json
  {
    "findings": [
      {
        "id": "hash(file+line+rule)",
        "reason": "Third-party library, cannot fix",
        "created_at": "2026-01-30T12:00:00Z"
      }
    ]
  }
  ```

**4. Diff Scanner** (`diff.py`)
- **Mode**: Incremental scanning (only changed files)
- **Use Case**: Pre-commit hooks, PR reviews
- **Backend**: `git diff --name-only`

---

#### 3.6 Librarian Subsystem (`src/librarian/`)

**CVE Knowledge Base**

**Data Sources:**
1. **Manual Models** (`manual_models.py`): Curated vulnerability patterns
2. **AI Fallback** (`ai_fallback.py`): LLM-based CVE lookup when DB misses
3. **External APIs**: NVD, OSV.dev (future integration)

**Version Resolution** (`version.py`)

**Algorithm**: Semantic versioning + range matching

**Example:**
```python
# Dependency: requests==2.25.0
# CVE-2023-12345 affects: requests >= 2.20.0, < 2.27.0
# Result: VULNERABLE ✗
```

**Typosquatting Detection** (`typosquat.py`)

**Method**: Levenshtein distance + popularity check

**Example:**
```python
# requirements.txt
import requestes  # ← Typo! Did you mean "requests"?
```

---

### 4. **Privacy Layer**

#### Masker (`src/core/privacy/masker.py`)

**GDPR Compliance**: Redact PII before sending to external LLMs

**Redaction Patterns:**
```python
REDACTION_RULES = {
    "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
    "phone": r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",
    "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
    "api_key": r"(api_key|apikey|api-key)\s*=\s*['\"]([^'\"]+)['\"]",
}
```

**Example:**
```python
# Before
code = 'api_key = "sk_live_abc123xyz"'

# After Masking
masked = 'api_key = "<REDACTED_API_KEY>"'
```

---

### 5. **Reporting Layer** (`src/report/`)

#### Report Manager (`manager.py`)

**Supported Formats:**

**1. SARIF** (`sarif.py`)
- **Standard**: OASIS SARIF 2.1.0
- **Integration**: GitHub Security tab, VS Code
- **Schema**:
  ```json
  {
    "version": "2.1.0",
    "runs": [{
      "tool": {"driver": {"name": "NSSS"}},
      "results": [{
        "ruleId": "sql-injection",
        "level": "error",
        "message": {"text": "Unsanitized user input flows to SQL query"},
        "locations": [{"physicalLocation": {"artifactLocation": {"uri": "app.py"}, "region": {"startLine": 42}}}]
      }]
    }]
  }
  ```

**2. Markdown** (`markdown.py`)
- **Format**: Human-readable summary
- **Sections**: Executive summary, findings by severity, remediation

**3. GraphViz** (`graph.py`)
- **Output**: DOT format → PNG/SVG
- **Use Case**: Visualize CFG, taint flow paths

**4. Debug IR** (`ir.py`)
- **Format**: JSON dump of full IR
- **Use Case**: Development, debugging

---

### 6. **Persistence Layer**

#### Graph Serializer (`src/core/persistence/graph_serializer.py`)

**Purpose**: Save/load NetworkX graphs for incremental analysis

**Storage Format**: GraphML (XML-based)

**Benefits:**
- **Incremental Analysis**: Reuse CFG from previous runs
- **Caching**: Avoid re-parsing unchanged files
- **Versioning**: Track graph changes over time

**Factory Pattern** (`factory.py`)

**Isolation Pattern**: Per-project persistence (no global state)

```python
# Create isolated persistence for project
persistence = create_project_persistence("/path/to/project")

# Save graph
persistence.save_graph(graph, "analysis_v1.graphml")

# Load graph
graph = persistence.load_graph("analysis_v1.graphml")
```

---

## Data Flow

### End-to-End Analysis Flow

```
┌─────────────────────────────────────────────────────────────┐
│ 1. INPUT: Python Source Files                               │
└─────────────────────────────────────────────────────────────┘
                      ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. PARSING: AST → IR (Pydantic Models)                      │
│    • Resolve imports (AliasResolver)                         │
│    • Detect obfuscation (base64, exec)                       │
│    • Extract SQL/NoSQL templates                             │
└─────────────────────────────────────────────────────────────┘
                      ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. CFG CONSTRUCTION: IR → NetworkX Graph                    │
│    • Model control flow (if/while/try/async)                │
│    • Build call graph (function → function edges)            │
└─────────────────────────────────────────────────────────────┘
                      ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. SSA TRANSFORMATION: Mutable → Immutable Variables        │
│    • Insert Phi nodes at merge points                        │
│    • Version all variable definitions                        │
└─────────────────────────────────────────────────────────────┘
                      ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. STATIC SCANNING: Semgrep + Secret Scanner                │
│    • Pattern-based rule matching                             │
│    • Hardcoded secret detection                              │
└─────────────────────────────────────────────────────────────┘
                      ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. DEPENDENCY ANALYSIS: Librarian CVE Lookup                │
│    • Parse requirements.txt / pyproject.toml                 │
│    • Match versions against CVE database                     │
│    • Detect typosquatting                                    │
└─────────────────────────────────────────────────────────────┘
                      ▼
┌─────────────────────────────────────────────────────────────┐
│ 7. TAINT ANALYSIS: Source → Sink Propagation                │
│    • Forward: Mark sources (request.GET, input())            │
│    • Propagate: Flow through assignments/calls               │
│    • Detect: Sanitizers (escape_html, quote)                 │
│    • Backward: Confirm sink reached by source                │
└─────────────────────────────────────────────────────────────┘
                      ▼
┌─────────────────────────────────────────────────────────────┐
│ 8. RISK ROUTING: Gatekeeper Decision                        │
│    • High-risk (implicit flows) → LLM                        │
│    • Low-risk (explicit flows) → Rules-only                  │
└─────────────────────────────────────────────────────────────┘
                      ▼
┌─────────────────────────────────────────────────────────────┐
│ 9. PRIVACY MASKING: Redact PII/Secrets                      │
│    • Email, phone, SSN → <REDACTED>                          │
│    • API keys, tokens → <REDACTED_API_KEY>                   │
└─────────────────────────────────────────────────────────────┘
                      ▼
┌─────────────────────────────────────────────────────────────┐
│ 10. LLM ANALYSIS: Semantic Verification (if high-risk)      │
│     • Extract semantic signature (source/sink code)          │
│     • Prompt LLM with context                                │
│     • Validate response via constrained decoder              │
│     • Cache result for future runs                           │
└─────────────────────────────────────────────────────────────┘
                      ▼
┌─────────────────────────────────────────────────────────────┐
│ 11. BASELINE FILTERING: Suppress Known FPs                  │
│     • Load .nsss_baseline.json                               │
│     • Match findings by hash(file+line+rule)                 │
│     • Filter out baselined findings                          │
└─────────────────────────────────────────────────────────────┘
                      ▼
┌─────────────────────────────────────────────────────────────┐
│ 12. REPORT GENERATION: SARIF / Markdown / Graph             │
│     • Group by severity (Critical, High, Medium, Low)        │
│     • Add remediation advice                                 │
│     • Export to configured format                            │
└─────────────────────────────────────────────────────────────┘
                      ▼
┌─────────────────────────────────────────────────────────────┐
│ 13. OUTPUT: Security Findings                               │
└─────────────────────────────────────────────────────────────┘
```

---

## Deployment Topologies

### Topology 1: Standalone (Local)

```
┌──────────────────┐
│  Developer       │
│  Laptop          │
├──────────────────┤
│  nsss-scan CLI   │
│  ↓               │
│  Local Analysis  │
│  ↓               │
│  Ollama (Local)  │  ← LLM running on localhost:11434
│  ↓               │
│  results.sarif   │
└──────────────────┘
```

**Pros:**
- No network required
- Full data sovereignty
- Fast (no API latency)

**Cons:**
- Requires GPU for LLM
- Limited to local model quality

---

### Topology 2: Low-Resource (Colab)

```
┌──────────────────┐               ┌──────────────────┐
│  Developer       │               │  Google Colab    │
│  Laptop          │     HTTPS     │  (Free Tier)     │
├──────────────────┤ ────────────► ├──────────────────┤
│  nsss-scan CLI   │               │  Qwen2.5-Coder   │
│  --remote-llm    │               │  (Inference API) │
│  https://xxx.    │               │  via ngrok       │
│  ngrok.io        │               │                  │
└──────────────────┘               └──────────────────┘
```

**Pros:**
- Zero-cost LLM inference
- No local GPU needed
- Accessible to students

**Cons:**
- Network latency
- Colab session timeout (12h)

---

### Topology 3: Enterprise (Self-hosted)

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  CI/CD Pipeline  │     │  LLM Gateway     │     │  Kubernetes      │
│  (GitHub Actions)│ ──► │  (Load Balancer) │ ──► │  (vLLM Pods)     │
├──────────────────┤     ├──────────────────┤     ├──────────────────┤
│  nsss-scan       │     │  Circuit Breaker │     │  Model: Qwen2.5  │
│  --format sarif  │     │  Cache Layer     │     │  Replicas: 3     │
└──────────────────┘     └──────────────────┘     └──────────────────┘
         │                                                  │
         ▼                                                  ▼
┌──────────────────┐                              ┌──────────────────┐
│  SIEM Integration│                              │  Prometheus      │
│  (Splunk, etc.)  │                              │  Metrics         │
└──────────────────┘                              └──────────────────┘
```

**Pros:**
- Production-grade reliability
- Scalable (horizontal scaling)
- Metrics & monitoring

**Cons:**
- Infrastructure overhead
- DevOps expertise required

---

## Extension Points

### 1. Plugin System

**File:** `src/core/pipeline/events.py`

**Interface:**
```python
from typing import Protocol

class PipelinePlugin(Protocol):
    def on_pipeline_started(self, context: AnalysisContext) -> None: ...
    def on_stage_completed(self, stage: str, context: AnalysisContext) -> None: ...
    def on_finding_detected(self, finding: Finding) -> None: ...
    def on_pipeline_completed(self, context: AnalysisContext) -> None: ...
```

**Registration:**
```python
from src.core.pipeline.events import register_plugin

register_plugin(MyCustomPlugin())
```

**Use Cases:**
- Custom metrics collection
- Slack/email notifications
- Custom finding filters

---

### 2. Custom Sanitizers

**File:** `src/core/analysis/sanitizers.py`

**Registration:**
```python
from src.core.analysis.sanitizers import SanitizerRegistry

registry = SanitizerRegistry()
registry.register(
    context="NOSQL",
    sanitizer_name="my_custom_sanitizer",
    effectiveness=1.0
)
```

---

### 3. Custom LLM Providers

**File:** `src/core/ai/client.py`

**Interface:**
```python
class AIClient(Protocol):
    async def analyze(self, request: AnalysisRequest) -> AnalysisResponse: ...
```

**Factory Registration:**
```python
from src.core.ai.client_factory import AIClientFactory

AIClientFactory.register_client(
    provider="my_provider",
    factory_fn=lambda config: MyCustomClient(config)
)
```

---

### 4. Custom Report Formats

**File:** `src/report/registry.py`

**Interface:**
```python
class ReportGenerator(Protocol):
    def generate(self, findings: List[Finding]) -> str: ...
```

**Registration:**
```python
from src.report.registry import ReportRegistry

ReportRegistry.register(
    format="my_format",
    generator=MyCustomReportGenerator()
)
```

---

## Technology Stack

### Core Runtime
- **Language**: Python 3.11+
- **Async**: asyncio + httpx
- **Type System**: Pydantic v2 (data validation)

### Analysis Libraries
- **Graph Processing**: NetworkX 3.x
- **AST Parsing**: Python `ast` module
- **Regex**: `re` + `regex` (advanced patterns)

### External Tools
- **Semgrep**: Pattern-based SAST
- **Ruff**: Linting + formatting
- **pytest**: Testing framework

### AI/ML
- **LLM Providers**: OpenAI, Google Gemini, Ollama
- **Future**: LangChain, LlamaIndex (RAG)

### Storage
- **Cache**: SQLite (LLM responses)
- **Graphs**: GraphML (NetworkX serialization)
- **Baseline**: JSON files

### Deployment
- **CLI**: Typer + Rich
- **Server**: Flask + ngrok
- **CI/CD**: GitHub Actions

---

## Design Principles

### 1. Engineering First, AI Second
- **Core analysis (CFG, SSA, taint)** does not depend on LLM availability
- LLM is used only for **semantic verification** of high-risk findings
- System degrades gracefully if LLM fails (circuit breaker fallback)

### 2. Protocol-Based Interfaces
- All major components implement Python `Protocol`
- Enables easy mocking in tests
- Supports dependency injection

### 3. Isolated State
- No global singletons
- All state passed via `AnalysisContext`
- Per-project persistence (no cross-contamination)

### 4. Event-Driven Architecture
- Pipeline emits lifecycle events
- Plugins hook into events without modifying core code
- Loose coupling → easier testing

### 5. Fail-Fast with Fallbacks
- Circuit breaker for LLM calls
- Cache fallback for network failures
- Rules-only mode if AI unavailable

---

## Performance Characteristics

### Benchmarks (on test project: 10 files, 1000 LOC)

| Stage | Time | Bottleneck |
|-------|------|------------|
| **Parsing** | 50ms | AST traversal |
| **CFG Build** | 100ms | Graph construction |
| **SSA Transform** | 80ms | Phi insertion |
| **Taint Analysis** | 200ms | DFS traversal |
| **LLM Analysis** | 2-5s | Network + inference |
| **Report Gen** | 30ms | JSON serialization |
| **TOTAL (with LLM)** | 2.5-5.5s | - |
| **TOTAL (rules-only)** | 500ms | - |

### Scalability
- **Linear**: CFG/SSA/Taint scale linearly with LOC
- **Parallel**: Can analyze multiple files concurrently
- **Cache**: 90%+ cache hit rate reduces LLM calls

---

## Security Considerations

### Threat Model

**Assumptions:**
- Attacker can submit malicious Python code for analysis
- Attacker cannot modify NSSS source code
- Attacker may attempt prompt injection via code comments

**Mitigations:**
1. **No Code Execution**: NSSS never runs `eval()` on analyzed code
2. **Prompt Guard**: LLM prompts sanitized via regex filters
3. **Constrained Decoding**: LLM outputs validated against JSON schema
4. **PII Masking**: Redact sensitive data before external LLM calls
5. **Secret Scanning**: Prevent accidental credential exposure

---

## Monitoring & Observability

### Metrics (`src/core/telemetry/metrics.py`)

**Exported Metrics:**
- `nsss_analysis_duration_seconds`: Total analysis time
- `nsss_llm_calls_total`: Number of LLM API calls
- `nsss_cache_hit_ratio`: Cache effectiveness
- `nsss_findings_by_severity`: Vulnerability counts

**Integration**: Prometheus-compatible `/metrics` endpoint (future)

### Logging (`src/core/telemetry/logger.py`)

**Structured Logging:**
```python
logger.info("taint_analysis_completed", extra={
    "duration_ms": 200,
    "paths_found": 5,
    "project": "/path/to/project"
})
```

**Log Levels:**
- `DEBUG`: Detailed execution trace
- `INFO`: High-level pipeline events
- `WARNING`: Recoverable errors (e.g., cache miss)
- `ERROR`: Unrecoverable errors (e.g., parse failure)

---

## Conclusion

The NSSS architecture balances **engineering rigor** with **AI innovation** to create a production-grade SAST system. Key design decisions:

1. **Modularity**: Each layer can be tested/replaced independently
2. **Extensibility**: Plugin system allows community contributions
3. **Reliability**: Circuit breaker + cache ensure robustness
4. **Privacy**: PII masking protects sensitive data
5. **Performance**: Caching + parallel processing minimize latency

**Future Evolution:**
- Graph Neural Networks (GNN) for vulnerability classification
- Incremental analysis for large monorepos
- IDE integration (VS Code extension)
- Multi-language support (JavaScript, Java, Go)

---

**Document Version:** 1.0  
**Last Updated:** January 30, 2026  
**Maintained By:** TCTri & NSSS Contributors
