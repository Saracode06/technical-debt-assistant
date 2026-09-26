# Technical Debt Detection & Remediation Assistant — Plan

## Top-Level Overview

Build a **self-contained, offline Python CLI tool** that scans a purposely-flawed sample
Python codebase, detects five categories of technical debt, explains each finding,
prioritizes by severity, generates remediated copies of the affected files, and then
validates the improvement with a before/after delta report.

No external APIs, credentials, datasets, network calls, or third-party packages are used.
Everything runs with Python's standard library (`ast`, `re`, `os`, `json`, `pathlib`,
`textwrap`). No `pytest`, `rich`, `click`, or any other external package is permitted.

**Hardcoded-secret samples use only clearly fake placeholder values** (e.g.
`"FAKE_SECRET_123"`, `"example-token"`). No real credentials of any kind appear anywhere.

The full pipeline is triggered from a single entry point: `main.py`.

### Remediation approach (confirmed)

All fixes are applied to copies under `output/patched/` — the original `sample_codebase/`
is never modified. Actual safe code fixes are applied where practical:

| Category | Remediation applied |
|---|---|
| Hardcoded secrets | Replace fake literal with `os.environ.get('VAR_NAME', '')` |
| Missing error handling | Wrap the risky call in a minimal `try/except` block |
| Dead code | Remove the unused import line or unused assignment entirely |
| Long functions | Extract the body into a clearly-named helper function (refactoring stub) |
| Code duplication | Extract the duplicate block into a shared helper function |

### Thresholds (confirmed)

- Long-function threshold: **40 lines**

---

## Repository Layout (target state)

```
technical-debt-assistant/
├── sample_codebase/          # Intentionally-bad Python source files
│   ├── auth.py
│   ├── data_processor.py
│   └── utils.py
├── scanner/
│   └── file_scanner.py       # Walk files, parse AST + raw text
├── detectors/
│   ├── base_detector.py      # Finding dataclass + base interface
│   ├── hardcoded_secrets.py
│   ├── long_functions.py
│   ├── code_duplication.py
│   ├── missing_error_handling.py
│   └── dead_code.py
├── engine/
│   └── prioritizer.py        # Score and rank all findings
├── remediator/
│   └── patch_generator.py    # Rewrite files with inline fixes
├── reporter/
│   └── report_writer.py      # Write Markdown report
├── main.py                   # CLI entry point
└── output/                   # Runtime-generated, git-ignored
    ├── report.md
    └── patched/
```

---

## Sub-Tasks

---

### Sub-Task 1 — Sample Codebase

**Status:** [ ] pending

**Intent**
Create three small Python source files under `sample_codebase/` that deliberately
contain all five debt categories. These files are the input for every subsequent
sub-task and must be stable before any detector is written.

**Expected Outcomes**
- `sample_codebase/auth.py` exists and contains: hardcoded secret, missing error handling.
- `sample_codebase/data_processor.py` exists and contains: long function, duplicate code block.
- `sample_codebase/utils.py` exists and contains: dead code (unused import, unused variable).
- Each file is valid Python (parses without syntax errors).

**Todo List**
1. Create `sample_codebase/__init__.py` (empty).
2. Write `sample_codebase/auth.py` with a hardcoded password string and a database call
   wrapped in no try/except.
3. Write `sample_codebase/data_processor.py` with a function exceeding 40 lines and a
   copy-pasted block of at least 6 identical lines appearing twice.
4. Write `sample_codebase/utils.py` with two unused imports and one variable that is
   assigned but never read.

**Relevant Context**
- Files must be syntactically valid so `ast.parse()` succeeds on each one.
- Keep content minimal — just enough to trigger each detector reliably.

---

### Sub-Task 2 — Scanner

**Status:** [ ] pending

**Intent**
Implement `scanner/file_scanner.py` — the component that walks `sample_codebase/`,
reads each `.py` file, and produces a structured in-memory model (filename, raw source,
parsed AST) consumed by all detectors.

**Expected Outcomes**
- `scanner/file_scanner.py` exports a `scan_directory(path) -> list[FileModel]` function.
- `FileModel` is a dataclass with fields: `path`, `source`, `tree` (AST node).
- Running the scanner against `sample_codebase/` returns exactly three `FileModel` objects.

**Todo List**
1. Create `scanner/__init__.py` (empty).
2. Define the `FileModel` dataclass.
3. Implement `scan_directory` using `pathlib.Path.rglob("*.py")`.
4. Skip files that fail `ast.parse()` (log a warning, continue).

**Relevant Context**
- Uses only `ast`, `pathlib`, `dataclasses` from stdlib.
- No detector logic here — pure I/O and parsing.

---

### Sub-Task 3 — Detectors

**Status:** [ ] pending

**Intent**
Implement the five debt-category detectors. Each detector is an independent module
that accepts a `FileModel` and returns a list of `Finding` objects.

**Expected Outcomes**
- `detectors/base_detector.py` defines the `Finding` dataclass:
  `(file, line, category, severity, description, suggestion)`.
- Five detector modules, each with a `detect(file_model) -> list[Finding]` function.
- Running all five detectors against the sample codebase produces at least one finding
  per category.

**Severity scale:** `critical` | `high` | `medium` | `low`

**Detector specifications:**

| Module | Technique | Trigger condition |
|--------|-----------|-------------------|
| `hardcoded_secrets.py` | Regex on assignment values | Variable name matches `password/secret/key/token` AND value is a non-empty string literal |
| `long_functions.py` | AST FunctionDef line span | Function body exceeds 40 lines |
| `code_duplication.py` | Sliding-window line hash | Any 6-line window hash appears more than once in the file |
| `missing_error_handling.py` | AST Call node inspection | Call to `open`, `connect`, `execute`, `request` not inside a Try node |
| `dead_code.py` | AST Import + Name visitor | Imported name never appears in a Load context; variable assigned but Load count == 0 |

**Todo List**
1. Create `detectors/__init__.py` (empty).
2. Write `detectors/base_detector.py` with the `Finding` dataclass.
3. Write `detectors/hardcoded_secrets.py`.
4. Write `detectors/long_functions.py`.
5. Write `detectors/code_duplication.py`.
6. Write `detectors/missing_error_handling.py`.
7. Write `detectors/dead_code.py`.

**Relevant Context**
- All detectors import `FileModel` from `scanner.file_scanner` and `Finding` from
  `detectors.base_detector`.
- Keep each detector under ~60 lines; prefer simple over clever.

---

### Sub-Task 4 — Prioritizer (Engine)

**Status:** [ ] pending

**Intent**
Implement `engine/prioritizer.py` to aggregate all findings from all detectors,
assign a numeric score, sort by score descending, and serialize to
`output/findings.json`.

**Expected Outcomes**
- `engine/prioritizer.py` exports `prioritize(findings: list[Finding]) -> list[Finding]`.
- Severity-to-score mapping: `critical=40`, `high=30`, `medium=20`, `low=10`.
- Output list is sorted highest score first.
- `output/findings.json` is written with all fields of each `Finding`.

**Todo List**
1. Create `engine/__init__.py` (empty).
2. Implement the severity score mapping.
3. Implement `prioritize()` — sort in place by score, return sorted list.
4. Add a helper `save_findings(findings, output_path)` that writes JSON.

**Relevant Context**
- `Finding` is a dataclass; use `dataclasses.asdict()` for JSON serialization.
- `output/` directory must be created if absent (`Path.mkdir(parents=True, exist_ok=True)`).

---

### Sub-Task 5 — Reporter

**Status:** [ ] pending

**Intent**
Implement `reporter/report_writer.py` to render the prioritized findings into a
human-readable Markdown report saved to `output/report.md`.

**Expected Outcomes**
- Report contains a summary table (category, count, highest severity).
- Each finding has its own section: file + line, description, suggestion.
- A "Validation" section at the end shows before/after issue counts when a
  `patched_findings` list is also supplied (optional second argument).

**Todo List**
1. Create `reporter/__init__.py` (empty).
2. Implement `write_report(findings, output_path, patched_findings=None)`.
3. Summary table: group findings by category, count per category, worst severity.
4. Detail section: one heading per finding with file, line, description, suggestion.
5. Validation section: if `patched_findings` supplied, print "Before: N  After: M  Resolved: N-M".

**Relevant Context**
- Pure string formatting — no templating library needed.
- `output/report.md` is git-ignored.

---

### Sub-Task 6 — Remediator

**Status:** [ ] pending

**Intent**
Implement `remediator/patch_generator.py` to apply actual safe code fixes (not just
comments) to copies of the affected source files, writing results to `output/patched/`.
The original `sample_codebase/` is never modified.

**Expected Outcomes**
- Patched copies of all affected files exist under `output/patched/` mirroring the
  original directory structure.
- **Hardcoded secrets:** the fake string literal is replaced in-line with
  `os.environ.get('VAR_NAME', '')`. An `import os` is prepended if not already present.
- **Missing error handling:** the risky call site is wrapped in a minimal
  `try: ... except Exception: pass` block, indented correctly to match the surrounding
  code.
- **Dead code — unused imports:** the entire import line is deleted.
- **Dead code — unused variables:** the assignment line is deleted.
- **Long functions:** a `# TODO: refactor — extract helper` comment is inserted directly
  above the function definition, and the function body is left intact (full structural
  extraction is beyond the safe scope of a text-level patcher; the comment serves as a
  clear refactoring stub visible in the report).
- **Code duplication:** the duplicate block is replaced by a call to a new helper
  function `_extracted_duplicate_block_N()`, and the helper definition is appended at
  the bottom of the patched file.
- Re-scanning `output/patched/` must resolve all findings that were actually fixed
  (secrets, dead code, duplication) and reduce — but not necessarily eliminate — the
  long-function and error-handling counts.

**Todo List**
1. Create `remediator/__init__.py` (empty).
2. Implement `generate_patches(findings, source_root, output_root)`:
   a. Copy every `.py` source file to `output_root`, preserving relative paths.
   b. Group findings by file so each patched file is rewritten in a single pass.
   c. Process findings from **last line to first line** within each file so earlier
      line-number references remain valid after insertions/deletions.
3. Per-category patch logic:
   - `hardcoded_secrets`: regex-replace the string literal on the target line; prepend
     `import os` if absent.
   - `missing_error_handling`: rewrite the target line(s) as a `try/except` block with
     correct indentation.
   - `dead_code` (import): delete the line.
   - `dead_code` (variable): delete the assignment line.
   - `long_functions`: insert a `# TODO: refactor — extract helper` comment above the
     `def` line.
   - `code_duplication`: collect the duplicate window lines, replace the second
     occurrence with a helper call, append the helper definition at end of file.
4. Return the list of patched file paths for downstream re-scanning.

**Relevant Context**
- Operate exclusively on the copies in `output/patched/` — never on the originals.
- Line numbers in `Finding` are 1-based (matching AST and editor conventions).
- Process findings bottom-up within each file to keep line references stable during
  multi-line insertions or deletions.
- `import os` injection for secrets: check the copied file's lines for an existing
  `import os` before prepending to avoid duplicates.

---

### Sub-Task 7 — CLI Entry Point & Validation Loop

**Status:** [ ] pending

**Intent**
Wire everything together in `main.py` with two sub-commands: `scan` (detect + report)
and `fix` (detect + patch + re-scan + validate report).

**Expected Outcomes**
- `python main.py scan` runs the full Scan → Detect → Explain → Prioritize → Report
  pipeline and prints a summary to stdout + writes `output/report.md`.
- `python main.py fix` additionally runs Remediate → re-scan patched files →
  appends validation delta to the report.
- Running `python main.py scan` with no arguments prints usage.
- Zero imports from outside stdlib.

**Todo List**
1. Parse `sys.argv[1]` for `scan` | `fix`.
2. `scan` flow: `scan_directory` → all detectors → `prioritize` → `save_findings` →
   `write_report`.
3. `fix` flow: same as `scan`, then `generate_patches` → re-run `scan_directory` on
   `output/patched/` → all detectors again → `prioritize` → `write_report` with
   `patched_findings`.
4. Print a one-line summary to stdout for each stage as it completes.

**Relevant Context**
- No `argparse` needed — a simple `if/elif` on `sys.argv` keeps it lean.
- The validation re-scan mirrors the initial scan, confirming the delta.

---

## Non-Goals

- No machine-learning or LLM-based detection.
- No web UI, no database, no network calls.
- No support for languages other than Python.
- No auto-merge of patches back into the original `sample_codebase/`.
- No external packages (`pytest`, `rich`, `click`, `requests`, etc.).
- No real credentials, API keys, passwords, or personal data anywhere in the project.

---

## Constraints (confirmed, non-negotiable)

- **Fake secrets only:** every hardcoded value in `sample_codebase/` is an obviously
  fake placeholder (e.g. `"FAKE_SECRET_123"`, `"example-token"`).
- **stdlib only:** the entire project must run with `python main.py` on a stock Python 3
  installation — no `pip install` step.
- **originals are immutable:** `sample_codebase/` files are never written to by the
  tool; all fixes go to `output/patched/`.
- **`output/` is git-ignored:** add `output/` to `.gitignore` during Sub-Task 7.

---

## Budget Notes

- All seven sub-tasks use stdlib only — no `pip install` ever needed.
- Sample codebase is hand-crafted and deterministic — no dataset downloads.
- Each sub-task is independently testable by reading `output/findings.json` or
  `output/report.md` after running `python main.py scan`.
