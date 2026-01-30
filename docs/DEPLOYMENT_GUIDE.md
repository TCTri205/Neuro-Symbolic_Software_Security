# NSSS Deployment & Usage Guide

**Version:** 2.3 Final  
**Last Updated:** January 30, 2026  
**Target Audience:** DevOps Engineers, Security Teams, Developers

---

## Table of Contents
1. [Quick Start](#quick-start)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Usage Examples](#usage-examples)
5. [Deployment Modes](#deployment-modes)
6. [CI/CD Integration](#cicd-integration)
7. [Troubleshooting](#troubleshooting)
8. [Best Practices](#best-practices)

---

## Quick Start

### 5-Minute Setup (Local Mode)

```bash
# 1. Clone repository
git clone https://github.com/your-org/Neuro-Symbolic_Software_Security.git
cd Neuro-Symbolic_Software_Security

# 2. Install dependencies
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# 3. Run your first scan (rules-only, no LLM required)
python -m src.runner.cli.main scan /path/to/your/project

# 4. View results
cat nsss_results.sarif
```

**Expected Output:**
```
✓ Analysis complete
  Files scanned: 15
  Findings: 3 Critical, 5 High, 2 Medium
  Report: nsss_results.sarif
```

---

## Installation

### Prerequisites

| Component | Version | Required | Notes |
|-----------|---------|----------|-------|
| **Python** | 3.10+ | Yes | Use 3.11 for best performance |
| **pip** | 20.0+ | Yes | For dependency management |
| **Git** | 2.0+ | Yes | For version control |
| **Semgrep** | 1.0+ | No | Auto-installed via pip |
| **Docker** | 20.0+ | No | For containerized deployment |
| **GPU** | CUDA 11.0+ | No | Only for local LLM inference |

---

### Installation Methods

#### Method 1: Standard Installation (Recommended)

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Verify installation
python -m src.runner.cli.main --version
```

**Expected Output:**
```
NSSS version 2.3.0
```

---

#### Method 2: Development Installation

```bash
# Install with dev dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install

# Run tests to verify
pytest
```

---

#### Method 3: Docker Installation

```bash
# Build Docker image
docker build -t nsss:2.3 .

# Run container
docker run -v /path/to/project:/project nsss:2.3 scan /project

# View results
docker cp <container_id>:/project/nsss_results.sarif .
```

**Dockerfile Example:**
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY docs/ ./docs/

ENTRYPOINT ["python", "-m", "src.runner.cli.main"]
```

---

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```bash
# LLM Configuration
OPENAI_API_KEY=sk-proj-...                    # OpenAI API key (optional)
GEMINI_API_KEY=AIza...                        # Google Gemini key (optional)
LLM_PROVIDER=openai                           # openai | gemini | ollama | mock
LLM_MODEL=gpt-4o-mini                         # Model name

# Ollama Configuration (for local LLM)
OLLAMA_BASE_URL=http://localhost:11434        # Ollama server URL
OLLAMA_MODEL=qwen2.5-coder:7b                 # Model to use

# Circuit Breaker
CIRCUIT_BREAKER_THRESHOLD=5                   # Failures before opening
CIRCUIT_BREAKER_TIMEOUT=60                    # Seconds before retry

# Cache Configuration
CACHE_ENABLED=true                            # Enable LLM response caching
CACHE_EXPIRY=86400                            # Cache TTL in seconds (24h)

# Logging
LOG_LEVEL=INFO                                # DEBUG | INFO | WARNING | ERROR
LOG_FORMAT=json                               # json | text

# Analysis Settings
MAX_TAINT_PATH_LENGTH=50                      # Max taint propagation depth
ENABLE_SPECULATIVE_EXPANSION=true             # Enable call graph speculation
ENABLE_BASELINE=true                          # Enable baseline filtering
```

---

### Configuration File (`nsss.yaml`)

For project-specific settings, create `nsss.yaml` in the project root:

```yaml
version: 2.3

# Analysis settings
analysis:
  enabled_scanners:
    - semgrep
    - secrets
    - taint
    - librarian
  
  excluded_paths:
    - "**/node_modules/**"
    - "**/venv/**"
    - "**/test/**"
    - "**/.git/**"
  
  taint:
    max_path_length: 50
    enable_backward_propagation: true
  
  llm:
    enabled: true
    routing_threshold: 0.7  # Risk score to trigger LLM analysis
    max_retries: 3

# Report settings
report:
  format: sarif  # sarif | markdown | json | graph
  output_file: nsss_results.sarif
  include_remediation: true
  severity_levels:
    - critical
    - high
    - medium
    # - low      # Uncomment to include low-severity findings

# Baseline
baseline:
  enabled: true
  file: .nsss_baseline.json
  auto_create: false

# Custom rules
custom_rules:
  - path: ./custom_semgrep_rules/
  - path: ./org_security_policies/
```

---

## Usage Examples

### Example 1: Basic Scan (Rules-Only)

**Scenario:** Quick scan without LLM (fastest, no API costs)

```bash
python -m src.runner.cli.main scan /path/to/project \
  --no-llm \
  --format sarif \
  --output results.sarif
```

**Output:**
```
📊 Scanning /path/to/project...
  ├── Parsing files... ✓ (15 files, 1.2s)
  ├── Building CFG... ✓ (0.8s)
  ├── SSA transformation... ✓ (0.5s)
  ├── Taint analysis... ✓ (1.0s)
  ├── Semgrep scan... ✓ (2.5s)
  ├── Secret scan... ✓ (0.3s)
  └── Report generation... ✓ (0.1s)

📈 Summary:
  Critical: 2
  High:     5
  Medium:   3
  Low:      1

📁 Report saved to: results.sarif
```

---

### Example 2: Full Scan with LLM Verification

**Scenario:** Deep analysis with AI semantic verification

```bash
export OPENAI_API_KEY=sk-proj-...

python -m src.runner.cli.main scan /path/to/project \
  --llm-provider openai \
  --llm-model gpt-4o-mini \
  --format markdown \
  --output report.md
```

**Output:**
```
📊 Scanning /path/to/project...
  ├── ... (same as above)
  ├── LLM analysis... ⏳ (analyzing 3 high-risk paths)
  │   ├── Path 1/3... ✓ (vulnerable, confidence: 0.95)
  │   ├── Path 2/3... ✓ (false positive, confidence: 0.12)
  │   └── Path 3/3... ✓ (vulnerable, confidence: 0.88)
  └── Report generation... ✓

📈 Summary:
  Critical: 2 (2 LLM-verified)
  High:     3 (1 FP filtered by LLM)

📁 Report saved to: report.md
```

---

### Example 3: Incremental Scan (Git Diff)

**Scenario:** Pre-commit hook or PR review

```bash
python -m src.runner.cli.main scan /path/to/project \
  --diff \
  --baseline .nsss_baseline.json
```

**Behavior:**
- Only scans files changed since last commit
- Filters findings already in baseline
- Fast (~500ms for small changes)

---

### Example 4: Low-Resource Mode (Laptop + Colab)

**Step 1: Start Colab Server**

In Google Colab:
```python
!git clone https://github.com/your-org/Neuro-Symbolic_Software_Security.git
%cd Neuro-Symbolic_Software_Security
!pip install -r requirements.txt

# Start server with ngrok tunnel
!python -m src.server.start_colab
```

**Expected Output:**
```
🚀 NSSS Inference Server
📡 Public URL: https://abc123.ngrok.io
✓ Ready to accept requests
```

**Step 2: Run Client on Laptop**

```bash
python -m src.runner.cli.main scan /path/to/project \
  --remote-llm https://abc123.ngrok.io
```

**Benefits:**
- Zero-cost LLM inference (Colab Free Tier)
- No local GPU required
- Suitable for students/researchers

---

### Example 5: CI/CD Integration (GitHub Actions)

**Scenario:** Automated scanning on every PR

**.github/workflows/security-scan.yml:**
```yaml
name: Security Scan

on:
  pull_request:
    branches: [main, develop]

jobs:
  nsss-scan:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install NSSS
        run: |
          pip install -r requirements.txt
      
      - name: Run security scan
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: |
          python -m src.runner.cli.main scan . \
            --format sarif \
            --output nsss-results.sarif \
            --diff
      
      - name: Upload SARIF to GitHub Security
        uses: github/codeql-action/upload-sarif@v2
        with:
          sarif_file: nsss-results.sarif
      
      - name: Fail on critical findings
        run: |
          CRITICAL=$(jq '.runs[0].results | map(select(.level=="error")) | length' nsss-results.sarif)
          if [ "$CRITICAL" -gt 0 ]; then
            echo "❌ Found $CRITICAL critical vulnerabilities"
            exit 1
          fi
```

**Result:**
- Automated scans on every PR
- Findings appear in GitHub Security tab
- PR blocked if critical vulnerabilities found

---

## Deployment Modes

### Mode 1: Developer Workstation

**Use Case:** Local development, pre-commit scanning

**Setup:**
```bash
# One-time setup
pip install -r requirements.txt

# Add to .git/hooks/pre-commit
#!/bin/bash
python -m src.runner.cli.main scan . --diff --quiet
if [ $? -ne 0 ]; then
  echo "❌ Security vulnerabilities found. Commit blocked."
  exit 1
fi
```

**Benefits:**
- Catch vulnerabilities before commit
- Fast (incremental scanning)
- No infrastructure required

---

### Mode 2: CI/CD Pipeline

**Use Case:** Automated scanning in GitHub Actions, GitLab CI, Jenkins

**Example: GitLab CI**

`.gitlab-ci.yml:`
```yaml
security-scan:
  stage: test
  image: python:3.11
  
  before_script:
    - pip install -r requirements.txt
  
  script:
    - python -m src.runner.cli.main scan . --format sarif --output nsss.sarif
  
  artifacts:
    reports:
      sast: nsss.sarif
  
  only:
    - merge_requests
    - main
```

---

### Mode 3: Centralized Security Server

**Use Case:** Enterprise security team scanning multiple projects

**Architecture:**
```
┌─────────────────────┐
│  Security Team      │
│  Control Center     │
└─────────────────────┘
          │
          ▼
┌─────────────────────┐
│  NSSS API Server    │
│  (Flask/FastAPI)    │
├─────────────────────┤
│  • Queue: Celery    │
│  • Cache: Redis     │
│  • LLM: vLLM        │
└─────────────────────┘
          │
          ▼
┌─────────────────────┐
│  Project Repos      │
│  (Auto-scanned)     │
└─────────────────────┘
```

**Benefits:**
- Centralized vulnerability dashboard
- Consistent security policies
- Resource pooling (shared LLM inference)

---

### Mode 4: Kubernetes Deployment

**Use Case:** Scalable, production-grade deployment

**Kubernetes Manifests:**

**1. Deployment (`nsss-deployment.yaml`):**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nsss-worker
spec:
  replicas: 3
  selector:
    matchLabels:
      app: nsss
  template:
    metadata:
      labels:
        app: nsss
    spec:
      containers:
      - name: nsss
        image: nsss:2.3
        env:
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: nsss-secrets
              key: openai-api-key
        - name: CACHE_ENABLED
          value: "true"
        resources:
          requests:
            memory: "2Gi"
            cpu: "1"
          limits:
            memory: "4Gi"
            cpu: "2"
```

**2. Service (`nsss-service.yaml`):**
```yaml
apiVersion: v1
kind: Service
metadata:
  name: nsss-api
spec:
  selector:
    app: nsss
  ports:
  - port: 80
    targetPort: 5000
  type: LoadBalancer
```

**3. ConfigMap (`nsss-config.yaml`):**
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: nsss-config
data:
  nsss.yaml: |
    analysis:
      enabled_scanners: [semgrep, secrets, taint]
    llm:
      provider: openai
      model: gpt-4o-mini
```

**Deploy:**
```bash
kubectl apply -f nsss-deployment.yaml
kubectl apply -f nsss-service.yaml
kubectl apply -f nsss-config.yaml
```

---

## CI/CD Integration

### GitHub Actions (Detailed)

**Strategy:** Fail-fast on critical vulnerabilities, warn on high/medium

```yaml
name: NSSS Security Scan

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  scan:
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v3
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
          cache: 'pip'
      
      - name: Install dependencies
        run: pip install -r requirements.txt
      
      - name: Run NSSS scan
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          LOG_LEVEL: INFO
        run: |
          python -m src.runner.cli.main scan . \
            --format sarif \
            --output nsss-results.sarif \
            --config nsss.yaml
      
      - name: Upload SARIF
        uses: github/codeql-action/upload-sarif@v2
        if: always()
        with:
          sarif_file: nsss-results.sarif
      
      - name: Analyze results
        id: analyze
        run: |
          CRITICAL=$(jq '[.runs[0].results[] | select(.level=="error")] | length' nsss-results.sarif)
          HIGH=$(jq '[.runs[0].results[] | select(.level=="warning")] | length' nsss-results.sarif)
          
          echo "critical=$CRITICAL" >> $GITHUB_OUTPUT
          echo "high=$HIGH" >> $GITHUB_OUTPUT
          
          echo "### Security Scan Results 🔒" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "- **Critical:** $CRITICAL" >> $GITHUB_STEP_SUMMARY
          echo "- **High:** $HIGH" >> $GITHUB_STEP_SUMMARY
      
      - name: Comment on PR
        if: github.event_name == 'pull_request'
        uses: actions/github-script@v6
        with:
          script: |
            const critical = ${{ steps.analyze.outputs.critical }};
            const high = ${{ steps.analyze.outputs.high }};
            
            let message = `## 🔒 NSSS Security Scan\n\n`;
            message += `- **Critical:** ${critical}\n`;
            message += `- **High:** ${high}\n\n`;
            
            if (critical > 0) {
              message += `❌ **Action Required:** Fix critical vulnerabilities before merging.\n`;
            } else {
              message += `✅ No critical vulnerabilities found.\n`;
            }
            
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: message
            });
      
      - name: Fail on critical findings
        if: steps.analyze.outputs.critical > 0
        run: |
          echo "❌ Found ${{ steps.analyze.outputs.critical }} critical vulnerabilities"
          exit 1
```

---

### Jenkins Pipeline

**Jenkinsfile:**
```groovy
pipeline {
    agent any
    
    environment {
        OPENAI_API_KEY = credentials('openai-api-key')
    }
    
    stages {
        stage('Setup') {
            steps {
                sh 'pip install -r requirements.txt'
            }
        }
        
        stage('Security Scan') {
            steps {
                sh '''
                    python -m src.runner.cli.main scan . \
                        --format sarif \
                        --output nsss-results.sarif
                '''
            }
        }
        
        stage('Analyze') {
            steps {
                script {
                    def results = readJSON file: 'nsss-results.sarif'
                    def critical = results.runs[0].results.count { it.level == 'error' }
                    
                    if (critical > 0) {
                        error("Found ${critical} critical vulnerabilities")
                    }
                }
            }
        }
    }
    
    post {
        always {
            archiveArtifacts artifacts: 'nsss-results.sarif', allowEmptyArchive: true
            publishHTML([
                reportDir: 'htmlcov',
                reportFiles: 'index.html',
                reportName: 'NSSS Report'
            ])
        }
    }
}
```

---

## Troubleshooting

### Issue 1: "ModuleNotFoundError: No module named 'src'"

**Cause:** Python can't find the `src` package

**Solution:**
```bash
# Option 1: Run from project root
cd /path/to/Neuro-Symbolic_Software_Security
python -m src.runner.cli.main scan .

# Option 2: Add to PYTHONPATH
export PYTHONPATH=/path/to/Neuro-Symbolic_Software_Security:$PYTHONPATH

# Option 3: Install in editable mode
pip install -e .
```

---

### Issue 2: "OpenAI API Error: Rate limit exceeded"

**Cause:** Too many LLM API calls

**Solution 1: Enable caching**
```bash
export CACHE_ENABLED=true
export CACHE_EXPIRY=86400  # 24 hours
```

**Solution 2: Use circuit breaker**
```bash
export CIRCUIT_BREAKER_THRESHOLD=3
export CIRCUIT_BREAKER_TIMEOUT=120
```

**Solution 3: Reduce LLM usage**
```yaml
# nsss.yaml
analysis:
  llm:
    routing_threshold: 0.9  # Only route very high-risk findings to LLM
```

---

### Issue 3: "Taint analysis timeout"

**Cause:** Large codebase with deep call graphs

**Solution:**
```yaml
# nsss.yaml
analysis:
  taint:
    max_path_length: 30  # Reduce from default 50
    timeout: 300         # 5 minutes max
```

---

### Issue 4: "Too many false positives"

**Solution 1: Create baseline**
```bash
# Initial scan (expect FPs)
python -m src.runner.cli.main scan . --output results.sarif

# Review results, mark FPs in .nsss_baseline.json manually
# Or use interactive mode:
python -m src.runner.cli.main baseline create

# Future scans will filter baselined findings
python -m src.runner.cli.main scan . --baseline .nsss_baseline.json
```

**Solution 2: Adjust sensitivity**
```yaml
# nsss.yaml
analysis:
  taint:
    sensitivity: medium  # low | medium | high
```

---

### Issue 5: "Semgrep not found"

**Cause:** Semgrep not installed

**Solution:**
```bash
pip install semgrep

# Or disable Semgrep
python -m src.runner.cli.main scan . --no-semgrep
```

---

## Best Practices

### 1. Start with Rules-Only Mode

```bash
# First run: Fast, no API costs
python -m src.runner.cli.main scan /project --no-llm

# Review findings, fix obvious issues
# Then enable LLM for remaining edge cases
python -m src.runner.cli.main scan /project --llm-provider openai
```

**Rationale:** 80% of vulnerabilities caught by rules, 20% need LLM

---

### 2. Use Baselines for Mature Projects

```bash
# For legacy codebases with many FPs:
# 1. Run initial scan
python -m src.runner.cli.main scan . --output initial.sarif

# 2. Manually review, create baseline
python -m src.runner.cli.main baseline create --input initial.sarif

# 3. Future scans use baseline
python -m src.runner.cli.main scan . --baseline .nsss_baseline.json
```

---

### 3. Enable Caching in Production

```yaml
# .env
CACHE_ENABLED=true
CACHE_EXPIRY=604800  # 7 days
CACHE_PATH=/var/cache/nsss/llm_cache.db
```

**Benefits:**
- 90%+ cache hit rate on unchanged code
- Reduce API costs by 10x
- Faster CI/CD pipelines

---

### 4. Use Diff Mode in CI/CD

```yaml
# GitHub Actions
- name: Scan changed files only
  run: python -m src.runner.cli.main scan . --diff
```

**Benefits:**
- 5-10x faster than full scans
- Focus on new vulnerabilities
- Suitable for pre-commit hooks

---

### 5. Segregate Secrets

```bash
# Never commit API keys!
# Use environment variables or secret managers

# Good:
export OPENAI_API_KEY=$(aws secretsmanager get-secret-value --secret-id nsss/openai --query SecretString --output text)

# Bad:
OPENAI_API_KEY=sk-proj-abc123  # ← NEVER DO THIS
```

---

### 6. Monitor LLM Usage

```python
# Add metrics collection plugin
from src.core.pipeline.events import register_plugin

class MetricsPlugin:
    def on_pipeline_completed(self, context):
        llm_calls = context.get("llm_calls", 0)
        cache_hits = context.get("cache_hits", 0)
        print(f"LLM calls: {llm_calls}, Cache hits: {cache_hits}")

register_plugin(MetricsPlugin())
```

---

### 7. Integrate with SIEM

```bash
# Export findings to SIEM
python -m src.runner.cli.main scan . --format json | \
  jq '.findings[] | select(.severity=="critical")' | \
  curl -X POST https://siem.company.com/api/events \
    -H "Content-Type: application/json" \
    -d @-
```

---

## Advanced Usage

### Custom Sanitizer Registration

```python
from src.core.analysis.sanitizers import SanitizerRegistry

# Register company-specific sanitizer
registry = SanitizerRegistry()
registry.register(
    context="SQL",
    sanitizer_name="our_custom_sql_escape",
    effectiveness=1.0
)
```

---

### Custom Plugin Development

```python
# my_plugin.py
from src.core.pipeline.events import register_plugin

class SlackNotificationPlugin:
    def on_pipeline_completed(self, context):
        findings = context["findings"]
        critical_count = len([f for f in findings if f.severity == "critical"])
        
        if critical_count > 0:
            self.send_slack_alert(critical_count)
    
    def send_slack_alert(self, count):
        # Send Slack webhook
        pass

# Register
register_plugin(SlackNotificationPlugin())
```

---

### Batch Scanning Multiple Projects

```bash
# scan_all.sh
#!/bin/bash

PROJECTS=(
    /repos/project-a
    /repos/project-b
    /repos/project-c
)

for project in "${PROJECTS[@]}"; do
    echo "Scanning $project..."
    python -m src.runner.cli.main scan "$project" \
        --format sarif \
        --output "results/$(basename $project).sarif"
done

# Merge results
jq -s '{"runs": [.[] | .runs[0]]}' results/*.sarif > combined.sarif
```

---

## Performance Tuning

### Optimize for Speed

```yaml
# nsss.yaml (fast mode)
analysis:
  taint:
    max_path_length: 20       # Reduce from 50
    enable_backward: false    # Skip backward propagation
  
  llm:
    enabled: false            # Rules-only
  
  parallel:
    enabled: true
    workers: 4                # Use all CPU cores
```

**Result:** 5-10x faster, but may miss complex vulnerabilities

---

### Optimize for Accuracy

```yaml
# nsss.yaml (thorough mode)
analysis:
  taint:
    max_path_length: 100      # Deep analysis
    enable_backward: true
  
  llm:
    enabled: true
    routing_threshold: 0.5    # Send more to LLM
    model: gpt-4              # Use best model
```

**Result:** Highest accuracy, but slower and more expensive

---

## Support & Resources

### Documentation
- **Quick Start:** [README.md](../README.md)
- **Architecture:** [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md)
- **Contribution:** [CONTRIB.md](CONTRIB.md)

### Community
- **Issues:** [GitHub Issues](https://github.com/your-org/Neuro-Symbolic_Software_Security/issues)
- **Discussions:** [GitHub Discussions](https://github.com/your-org/Neuro-Symbolic_Software_Security/discussions)

### Commercial Support
Contact: security@your-org.com

---

**Last Updated:** January 30, 2026  
**Version:** 2.3 Final  
**Maintained By:** NSSS Team
