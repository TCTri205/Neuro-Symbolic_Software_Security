# 15. Baseline Engine Specification

This document defines the baseline engine used to suppress existing findings and only report new issues.

## 1. Goals

* Reduce alert fatigue by ignoring known findings.
* Support "diff-only" reporting for PR workflows.
* Keep baseline storage lightweight and deterministic.

## 2. Baseline File

Baseline data is stored at:

```
.nsss/baseline.json
```

### 2.1. Baseline Schema

```json
{
  "version": "1.0",
  "generated_at": "2026-01-28T10:00:00Z",
  "project_root": "/path/to/repo",
  "entries": [
    {
      "fingerprint": "PYTHON-SQL-INJECTION-001|src/auth/login.py|15|cursor.execute|user_input|a1b2c3",
      "rule_id": "PYTHON-SQL-INJECTION-001",
      "file": "src/auth/login.py",
      "line": 15,
      "column": 4,
      "sink": "cursor.execute",
      "source": "user_input",
      "code_hash": "a1b2c3",
      "created_at": "2026-01-28T10:00:00Z"
    }
  ]
}
```

### 2.2. Fingerprint Strategy

Fingerprint should be stable across runs and resilient to minor formatting changes:

```
fingerprint = rule_id + file + line + column + sink + source + code_hash
```

`code_hash` is SHA-256 of a normalized snippet around the finding (strip trailing whitespace, keep original line order).

`line` and `column` should be sourced from IR `Node.span` (`docs/07_IR_Schema.md`) to keep consistency across runs.

## 3. Workflow

### 3.1. Generate Baseline

* Run a full scan.
* All findings are written to `.nsss/baseline.json`.
* Subsequent scans treat these as known issues.

### 3.2. Filtering

For each finding:

* If `fingerprint` is in baseline -> mark as `existing` and suppress from report.
* If not -> mark as `new` and include in report.

### 3.3. Resolved Findings

If a baseline entry is not observed in a scan, mark it as `resolved` (optional list in debug output). Do not remove by default to keep audit history.

## 4. Reporting

`nsss_debug.json` should include counts:

```json
{
  "baseline": {
    "total": 120,
    "new": 5,
    "existing": 115,
    "resolved": 3
  }
}
```

SARIF should only include `new` findings when baseline mode is enabled.

## 5. CLI / Config (Draft)

* `--baseline` generate baseline.
* `--baseline-only` suppress existing findings.
* `--baseline-reset` regenerate baseline file.

## 6. Tasks

* Implement `BaselineEngine` in `src/core/scan/baseline.py`.
* Add unit tests for fingerprint stability and filtering behavior.
