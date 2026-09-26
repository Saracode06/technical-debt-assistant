"""app.py — Flask web interface for the Technical Debt Assistant.

Exposes the existing scan/fix pipeline over HTTP without duplicating any
detection or remediation logic.

Usage:
    python app.py          # starts on http://127.0.0.1:5000
"""

from pathlib import Path
from flask import Flask, jsonify, render_template

from scanner.file_scanner import scan_directory
from detectors.hardcoded_secrets import detect as detect_secrets
from detectors.long_functions import detect as detect_long_functions
from detectors.code_duplication import detect as detect_duplication
from detectors.missing_error_handling import detect as detect_error_handling
from detectors.dead_code import detect as detect_dead_code
from engine.prioritizer import prioritize, save_findings
from reporter.report_writer import write_report
from remediator.patch_generator import generate_patches

app = Flask(__name__)

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


def _severity_counts(findings):
    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for f in findings:
        if f.severity in counts:
            counts[f.severity] += 1
    return counts


def _finding_to_dict(f):
    return {
        "file": f.file,
        "line": f.line,
        "category": f.category,
        "severity": f.severity,
        "description": f.description,
        "suggestion": f.suggestion,
    }


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/scan", methods=["POST"])
def api_scan():
    """Run the full scan pipeline and return structured JSON results."""
    try:
        files = scan_directory(_SAMPLE_DIR)
        raw = _run_detectors(files)
        ranked = prioritize(raw)

        save_findings(ranked, _FINDINGS_JSON)
        write_report(ranked, _REPORT_MD)

        counts = _severity_counts(ranked)
        findings_list = [_finding_to_dict(f) for f in ranked]

        return jsonify({
            "status": "ok",
            "total": len(ranked),
            "counts": counts,
            "findings": findings_list,
        })
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


@app.route("/api/fix", methods=["POST"])
def api_fix():
    """Run the full remediation + validation pipeline and return before/after JSON."""
    try:
        # --- Before: scan original ---
        files = scan_directory(_SAMPLE_DIR)
        raw = _run_detectors(files)
        before_ranked = prioritize(raw)
        save_findings(before_ranked, _FINDINGS_JSON)

        # --- Patch ---
        generate_patches(before_ranked, Path(_SAMPLE_DIR), _PATCHED_DIR)

        # --- After: scan patched ---
        patched_files = scan_directory(str(_PATCHED_DIR))
        patched_raw = _run_detectors(patched_files)
        after_ranked = prioritize(patched_raw)

        write_report(before_ranked, _REPORT_MD, patched_findings=after_ranked)

        before = len(before_ranked)
        after = len(after_ranked)
        resolved = max(before - after, 0)

        return jsonify({
            "status": "ok",
            "before": before,
            "after": after,
            "resolved": resolved,
            "before_counts": _severity_counts(before_ranked),
            "after_counts": _severity_counts(after_ranked),
            "before_findings": [_finding_to_dict(f) for f in before_ranked],
            "after_findings": [_finding_to_dict(f) for f in after_ranked],
        })
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


if __name__ == "__main__":
    app.run(debug=False, host="127.0.0.1", port=5000)
