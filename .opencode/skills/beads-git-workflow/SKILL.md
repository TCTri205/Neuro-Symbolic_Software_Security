---
name: beads-git-workflow
description: Fully autonomous end-to-end workflow for NSSS tasks. Handles Beads issue tracking, TDD, Git version control, and GitHub PRs.
version: 1.2.0
compatibility: opencode
metadata:
  workflow: autonomous
  audience: developers
  risk_level: high
---

# Beads-Git Workflow (Autonomous Mode)

## ⚠️ Operational Rules (READ FIRST)
1.  **NO INTERACTIVE PROMPTS**: You are in **AUTONOMOUS MODE**. Do not ask the user for permission to run `bd`, `git`, or `pytest` commands.
2.  **FAIL FAST**: If a pre-flight check fails, abort immediately with a clear error message. Do not ask "Should I continue?".
3.  **SELF-CORRECTION**: If a test fails, you MUST try to fix the code up to 3 times before giving up.
4.  **CLEANUP**: Never leave the repository in a broken state. If you abort, run `git reset --hard` to restore the last clean state (unless you saved a patch).

## Phase 0: Pre-flight Assertions
**Goal**: Guarantee a clean environment. **Abort if ANY check fails.**

1.  **Assert Clean Git State**:
    ```bash
    if [ -n "$(git status --porcelain)" ]; then echo "❌ DIRTY_TREE: Commit or stash changes first."; exit 1; fi
    ```

2.  **Assert Single Context (Ignoring Epics)**:
    ```bash
    # Count active non-epic tasks
    COUNT=$(bd list --status=in_progress --json | python3 -c "import sys, json; data=json.load(sys.stdin); tasks=[i for i in data if i.get('issue_type') != 'epic']; print(len(tasks))")
    if [ "$COUNT" -gt 1 ]; then echo "❌ MULTI_TASK: $COUNT active tasks found. Resolve manually."; exit 1; fi
    ```
    *   *Result*: If `COUNT == 1`, set `RESUME_MODE=true`. If `COUNT == 0`, set `RESUME_MODE=false`.

3.  **Assert Remote Sync**:
    ```bash
    git fetch origin
    git status -uno
    ```
    *   *Action if Behind*: Run `git pull --rebase`. If conflict -> **ABORT**.

4.  **Assert GitHub Auth (If PR needed)**:
    ```bash
    if gh auth status >/dev/null 2>&1; then echo "GH_AUTH_OK"; else echo "⚠️ GH_AUTH_MISSING: PR creation will be skipped."; fi
    ```

## Phase 1: Auto-Discovery (Non-Interactive)
**Goal**: Select and claim the highest priority task automatically.

*Skip this phase if `RESUME_MODE=true`.*

1.  **Select Task**:
    ```bash
    bd ready
    ```
    *   *Logic*:
        1.  Pick **P0** (Critical) first.
        2.  If no P0, pick the **oldest P1**.
        3.  If list empty: **ABORT** "No ready work."

2.  **Claim**:
    ```bash
    bd update <ID> --claim
    ```

3.  **Load Context**:
    ```bash
    bd show <ID>
    ```
    *   *Rule*: If description mentions "IR", "Schema", or "Graph", you MUST read `docs/07_IR_Schema.md`.

## Phase 2: Design & Strategy
**Goal**: Identify integration points without user input.

1.  **Auto-Classification**:
    *   **Parser Task**: Target `src/core/parser`.
    *   **CFG Task**: Target `src/core/cfg`.
    *   **Plugin Task**: Target `src/plugins`.

2.  **Find Integration Point**:
    *   Run `grep` to find the file. Do not ask "Is this the right file?". Trust your heuristic.

3.  **Schema Impact Check**:
    *   Scan requirements for keywords: "new node", "new edge", "attribute".
    *   If found: Add "Update Schema Docs" to your internal TODO list.

## Phase 3: Test-First Development (Mandatory)
**Goal**: Define success via code.

1.  **Generate Test**:
    *   Create `tests/core/<module>/test_<feature>.py`.
    *   Use the **Inline Source Pattern** (see `prompts/test-gen.txt`).

2.  **Assert Failure**:
    ```bash
    pytest tests/core/<module>/test_<feature>.py
    ```
    *   *Rule*: If this PASSES, your test is invalid (false positive). Rewrite the test.

## Phase 4: Implementation Loop
**Goal**: Make the test pass.

1.  **Implement**: Write code in `src/`.
2.  **Verify**: `pytest tests/core/<module>/test_<feature>.py -vv`.
3.  **Retry Logic**:
    *   **Attempt 1**: Failed? Read error. Fix code. Retry.
    *   **Attempt 2**: Failed? Read error. Fix code. Retry.
    *   **Attempt 3**: Failed? **STOP**. Go to Emergency Procedure A.

## Phase 5: Quality Gates (Auto-Fix)
**Goal**: Enforce standards.

1.  **Format**: `make format` (Apply fixes silently).
2.  **Lint**: `make lint`.
    *   If fail: Fix the specific line. Do not ignore.
3.  **Regression**: `pytest tests/core/<module>/`.

## Phase 6: Delivery
**Goal**: Ship it.

1.  **Commit**:
    *   Generate message using `prompts/commit-msg-gen.txt`.
    *   `git add .`
    *   `git commit -m "..."`

2.  **Schema Update**:
    *   If Schema changed (from Phase 2), update `docs/07_IR_Schema.md`.
    *   `git commit --amend --no-edit`

3.  **Push**:
    ```bash
    bd sync
    git push origin main
    ```

4.  **GitHub PR (Conditional)**:
    *   **Trigger**: If `PR_MODE=1` or user requested.
    ```bash
    gh pr create --fill && gh run watch
    ```

5.  **Close**:
    ```bash
    bd close <ID>
    bd sync
    ```

---

# Emergency Procedures

## Procedure A: Rollback (Test Failure)
**Trigger**: Phase 4 fails 3 times.
**Action**:
1.  `git diff > failed_impl.patch`
2.  `git reset --hard`
3.  `git clean -fd`
4.  Log: "❌ Task failed. Patch saved to failed_impl.patch. Aborting."
5.  Exit.

## Procedure B: Conflict (Git Push)
**Trigger**: Git push rejected.
**Action**:
1.  `git pull --rebase`
2.  If conflicts: **ABORT**. Log: "❌ Merge conflict detected. Resolve manually."
