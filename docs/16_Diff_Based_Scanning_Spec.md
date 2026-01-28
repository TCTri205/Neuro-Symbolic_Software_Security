# 16. Diff-Based Scanning Specification

This document defines diff-based scanning for incremental analysis.

## 1. Goals

* Re-scan only changed files and their dependents.
* Reuse cached graphs for unchanged files.
* Keep fallback to full scan when dependency data is missing.

## 2. Inputs

* Git diff list between `base` and `HEAD` (or last scan).
* Graph persistence cache (`docs/11_Graph_Persistence_Spec.md`).
* Import graph or dependency map for reverse lookup, derived from IR `Import` nodes and `Symbol` table when available.

## 3. Change Detection

### 3.1. Changed Files

Default source is git:

```
git diff --name-only <base>...HEAD
```

Filter to supported extensions (e.g., `.py`).

### 3.2. File Hashing

Use SHA-256 for each file and compare with `manifest.json`.

## 4. Reverse Dependency Lookup

For Python, build a dependency map based on IR `Import` nodes and `Symbol` entries:

* `module -> imported_by[]`
* When `module` changes, re-scan all `imported_by` files.

If dependency data is missing, fall back to scanning all files.

### 4.1. IR Alignment

* `Import` node attrs (`module`, `names`, `asnames`) are the authoritative source for dependency extraction.
* `Symbol` entries with `kind=import` can be used to resolve aliasing and map to canonical modules.

## 5. Scan Algorithm

1. Load manifest and dependency map.
2. Identify changed files.
3. Compute impacted set: changed files + reverse dependencies.
4. For impacted files:
   * Parse and rebuild graphs.
   * Update cache and manifest.
5. For unchanged files:
   * Load graphs from cache.
6. Merge graphs into the project-level IR.

## 6. Output and Reporting

Only findings from impacted files are re-evaluated. Unchanged findings can be loaded from cached results if available.

## 7. Failure Modes

* If cache is missing or invalid -> full scan.
* If dependency graph is stale -> full scan or conservative re-scan of all modules.

## 8. Tasks

* Implement `DiffScanner` in `src/core/scan/diff.py`.
* Add unit tests for impacted set computation.
