# Technical Debt Detection & Remediation Assistant

An automated tool that scans Python source code, detects five categories of technical debt, prioritizes findings by severity, applies safe inline patches, and produces a before/after validation report — all using only the Python standard library.

Built for the **IBM Bob 2.0 Hackathon** using IBM Bob as the AI pair-programming assistant throughout development.

---

## The Problem

Technical debt accumulates silently. Hardcoded credentials sit in version control, unused imports pile up, copy-pasted blocks diverge over time, unprotected network calls crash in production, and oversized functions become impossible to maintain. Developers rarely have time to hunt these down systematically. This assistant automates that audit and applies concrete fixes in one command.

---

## Workflow

```
scan_directory → detect (5 detectors) → prioritize → save findings.json
                                                     ↓
                                               write report.md
                                                     ↓
                                          generate_patches → output/patched/
                                                     ↓
                                         re-scan patched files
                                                     ↓
                                      write validated report.md (before/after)
```

1. **Scan** — `scanner/file_scanner.py` walks the source tree and parses every `.py` file into an AST + source model.
2. **Detect** — Five independent detectors run against each file model and emit structured `Finding` objects.
3. **Prioritize** — `engine/prioritizer.py` assigns numeric scores (critical=40, high=30, medium=20, low=10) and sorts findings highest-first.
4. **Remediate** — `remediator/patch_generator.py` copies source files to `output/patched/` and applies inline fixes, bottom-up by line number so earlier edits do not invalidate later line references.
5. **Validate** — The patched directory is re-scanned with the same detectors; the delta (resolved, new issues) is written to the report.

---

## Five Debt Categories

| Category | Severity | What it detects | Fix applied |
|---|---|---|---|
| `hardcoded_secrets` | critical | String-literal passwords, tokens, keys assigned to sensitive variable names | Replace with `os.environ.get('VAR', '')` and inject `import os` |
| `missing_error_handling` | high | `connect()`, `open()`, `execute()` calls not inside a `try/except` | Wrap the call in `try: … except Exception: pass` |
| `code_duplication` | high | Identical 6-line normalised windows appearing more than once | Replace duplicate block with a stub helper call; append `_extracted_block_N()` definition |
| `long_functions` | medium | Functions whose line span exceeds 40 lines | Insert `# TODO: refactor — extract helper` above the `def` |
| `dead_code` | low | Unused imports and variables assigned but never read within their scope | Delete the unused import or assignment line |

---

## Requirements

- Python 3.8 or later (standard library only — no `pip install` needed)

---

## How to Run

### Scan only — detect and report, do not modify anything

```bash
python main.py scan
```

Output:
- `output/findings.json` — all findings as structured JSON
- `output/report.md` — human-readable report with summary table and per-finding details

### Fix — scan, patch, re-scan, validate

```bash
python main.py fix
```

Output:
- `output/patched/` — fixed copies of every source file (originals in `sample_codebase/` are **never** modified)
- `output/report.md` — updated report with a Validation section showing before/after counts per category

---

## Measurable Before / After Result

Running `python main.py fix` against the included `sample_codebase/` produces:

| Category | Before | After | Resolved |
|---|---|---|---|
| `hardcoded_secrets` | 1 | 0 | **1** |
| `missing_error_handling` | 1 | 0 | **1** |
| `code_duplication` | 2 | 0 | **2** |
| `long_functions` | 1 | 1 | 0 |
| `dead_code` | 5 | 1 | **4** |
| **Total** | **10** | **2** | **8** |

**8 of 10 findings resolved automatically.** The 2 remaining findings are:
- `long_functions` — a TODO comment is inserted; full refactoring requires human judgement.
- `dead_code` (1 residual) — when the duplicate block is extracted, the variable that fed only that block (`normalised` in `process_audit_records`) becomes orphaned. This is the expected and tested residual.

---

## Running the Tests

```bash
python -m unittest tests/test_suite.py -v
```

47 tests across 8 test classes covering scanner, all five detectors, prioritizer, reporter, remediator, and end-to-end integration. All tests use only the Python standard library.

---

## Project Structure

```
technical-debt-assistant/
├── main.py                        # CLI entry point (scan / fix)
├── sample_codebase/               # Intentionally-flawed source files (read-only)
│   ├── auth.py                    # hardcoded secret, missing error handling, dead_code
│   ├── data_processor.py          # long function, code duplication
│   └── utils.py                   # unused imports, unused variable
├── scanner/
│   └── file_scanner.py            # Walks directory, parses AST
├── detectors/
│   ├── base_detector.py           # Finding dataclass
│   ├── hardcoded_secrets.py       # Critical-severity detector
│   ├── long_functions.py          # Medium-severity detector
│   ├── code_duplication.py        # High-severity detector
│   ├── missing_error_handling.py  # High-severity detector
│   └── dead_code.py               # Low-severity detector
├── engine/
│   └── prioritizer.py             # Scoring and sorting
├── remediator/
│   └── patch_generator.py         # Inline patch application
├── reporter/
│   └── report_writer.py           # Markdown report writer
├── tests/
│   └── test_suite.py              # 47 unit + integration tests
└── output/                        # Generated at runtime
    ├── findings.json
    ├── report.md
    └── patched/                   # Fixed file copies
```

---

## Use of IBM Bob

IBM Bob was used as the AI pair-programming assistant throughout the entire project:

- **Architecture design** — Bob helped plan the pipeline (scanner → detectors → prioritizer → remediator → reporter) and the `Finding` dataclass schema.
- **Detector implementation** — Bob drafted and refined all five AST-based detectors, with particular attention to the dead_code scope analysis and the sliding-window duplication algorithm.
- **Remediator logic** — Bob implemented the bottom-up patch application strategy, the `_dedup_dup_findings` deduplication, and diagnosed and fixed the `results.append(entry)` survival bug in the code-duplication remediator.
- **Test suite** — Bob wrote the full 47-test suite covering unit, integration, and end-to-end scenarios.
- **Documentation** — Bob authored this README and the inline code comments.

All Bob session histories are preserved in `bob_sessions/`.
