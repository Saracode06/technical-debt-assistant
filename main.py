"""main.py — CLI entry point for the Technical Debt Assistant.

Usage:
    python main.py scan   # detect + prioritize + report
    python main.py fix    # detect + patch + re-scan + validated report
"""

import sys
from pathlib import Path

from scanner.file_scanner import scan_directory
from detectors.hardcoded_secrets import detect as detect_secrets
from detectors.long_functions import detect as detect_long_functions
from detectors.code_duplication import detect as detect_duplication
from detectors.missing_error_handling import detect as detect_error_handling
from detectors.dead_code import detect as detect_dead_code
from engine.prioritizer import prioritize, save_findings
from reporter.report_writer import write_report
from remediator.patch_generator import generate_patches

_SAMPLE_DIR = "sample_codebase"
_OUTPUT_DIR = Path("output")
_FINDINGS_JSON = _OUTPUT_DIR / "findings.json"
_REPORT_MD = _OUTPUT_DIR / "report.md"
_PATCHED_DIR = _OUTPUT_DIR / "patched"

_DETECTORS = [
    detect_secrets,
    detect_long_functions,
    detect_duplication,
    detect_error_handling,
    detect_dead_code,
]


def _run_detectors(file_models):
    findings = []
    for file_model in file_models:
        for detector in _DETECTORS:
            findings.extend(detector(file_model))
    return findings


def _severity_breakdown(findings):
    counts = {}
    for f in findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1
    order = ["critical", "high", "medium", "low"]
    parts = [f"{sev}={counts[sev]}" for sev in order if sev in counts]
    return "  ".join(parts)


def cmd_scan():
    print("[scan] Scanning source files ...")
    files = scan_directory(_SAMPLE_DIR)
    print(f"[scan] Found {len(files)} file(s) in '{_SAMPLE_DIR}'")

    print("[scan] Running detectors ...")
    raw = _run_detectors(files)
    print(f"[scan] {len(raw)} raw finding(s) detected")

    print("[scan] Prioritizing findings ...")
    ranked = prioritize(raw)
    print(f"[scan] Findings ranked ({_severity_breakdown(ranked)})")

    print(f"[scan] Saving findings to {_FINDINGS_JSON} ...")
    save_findings(ranked, _FINDINGS_JSON)
    print(f"[scan] Saved {len(ranked)} finding(s) to {_FINDINGS_JSON}")

    print(f"[scan] Writing report to {_REPORT_MD} ...")
    write_report(ranked, _REPORT_MD)
    print(f"[scan] Report written to {_REPORT_MD}")

    print()
    print(f"=== SCAN COMPLETE ===  Total findings: {len(ranked)}  |  {_severity_breakdown(ranked)}")
    return ranked


def cmd_fix():
    ranked = cmd_scan()

    print()
    print("[fix] Generating patches ...")
    generate_patches(ranked, Path(_SAMPLE_DIR), _PATCHED_DIR)
    print(f"[fix] Patched files written to {_PATCHED_DIR}")

    print("[fix] Re-scanning patched files ...")
    patched_files = scan_directory(str(_PATCHED_DIR))
    print(f"[fix] Found {len(patched_files)} patched file(s)")

    print("[fix] Running detectors on patched files ...")
    patched_raw = _run_detectors(patched_files)
    print(f"[fix] {len(patched_raw)} finding(s) in patched codebase")

    print("[fix] Prioritizing patched findings ...")
    patched_ranked = prioritize(patched_raw)

    print(f"[fix] Rewriting report with validation delta to {_REPORT_MD} ...")
    write_report(ranked, _REPORT_MD, patched_findings=patched_ranked)
    print(f"[fix] Report updated with before/after validation section")

    before = len(ranked)
    after = len(patched_ranked)
    resolved = max(before - after, 0)
    print()
    print(
        f"=== FIX COMPLETE ===  Before: {before}  After: {after}  "
        f"Resolved: {resolved}  |  {_severity_breakdown(patched_ranked)}"
    )


def _usage():
    print("Usage: python main.py <command>")
    print()
    print("Commands:")
    print("  scan   Scan sample_codebase, detect debt, write output/report.md")
    print("  fix    Scan, patch, re-scan, write validated output/report.md")


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("scan", "fix"):
        _usage()
        sys.exit(1)

    if sys.argv[1] == "scan":
        cmd_scan()
    else:
        cmd_fix()


if __name__ == "__main__":
    main()
