from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict


_SEVERITY_ORDER = ["critical", "high", "medium", "low"]


def _worst_severity(severities):
    for s in _SEVERITY_ORDER:
        if s in severities:
            return s
    return severities[0] if severities else "unknown"


def write_report(findings, output_path, patched_findings=None):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines = []

    # --- Header ---
    lines.append("# Technical Debt Report")
    lines.append("")
    lines.append(f"**Project:** sample_codebase  ")
    lines.append(f"**Scan timestamp:** {timestamp}  ")
    lines.append(f"**Total findings:** {len(findings)}")
    lines.append("")

    # --- Summary table ---
    lines.append("## Summary")
    lines.append("")
    lines.append("| Category | Count | Highest Severity |")
    lines.append("|---|---|---|")

    by_category = defaultdict(list)
    for f in findings:
        by_category[f.category].append(f)

    for category in sorted(by_category):
        group = by_category[category]
        worst = _worst_severity([f.severity for f in group])
        lines.append(f"| {category} | {len(group)} | {worst} |")

    lines.append("")

    # --- Details ---
    lines.append("## Findings")
    lines.append("")

    for i, f in enumerate(findings, start=1):
        lines.append(f"### {i}. [{f.severity.upper()}] {f.category}")
        lines.append("")
        lines.append(f"- **File:** `{f.file}`")
        lines.append(f"- **Line:** {f.line}")
        lines.append(f"- **Category:** {f.category}")
        lines.append(f"- **Severity:** {f.severity}")
        lines.append(f"- **Description:** {f.description}")
        lines.append(f"- **Suggestion:** {f.suggestion}")
        lines.append("")

    # --- Validation ---
    if patched_findings is not None:
        before = len(findings)
        after = len(patched_findings)
        resolved = max(before - after, 0)
        new_issues = max(after - before, 0)

        lines.append("## Validation")
        lines.append("")
        lines.append(
            f"Before: {before}  After: {after}  "
            f"Resolved: {resolved}  New: {new_issues}"
        )
        lines.append("")

        patched_by_category = defaultdict(list)
        for f in patched_findings:
            patched_by_category[f.category].append(f)

        all_categories = sorted(set(by_category) | set(patched_by_category))
        lines.append("| Category | Before | After | Resolved |")
        lines.append("|---|---|---|---|")
        for category in all_categories:
            b = len(by_category[category])
            a = len(patched_by_category[category])
            r = max(b - a, 0)
            lines.append(f"| {category} | {b} | {a} | {r} |")
        lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")
