import json
import dataclasses
from pathlib import Path

_SEVERITY_SCORE = {
    "critical": 40,
    "high": 30,
    "medium": 20,
    "low": 10,
}


def prioritize(findings):
    """Assign a numeric score by severity and return sorted list (highest first)."""
    for f in findings:
        f.score = _SEVERITY_SCORE.get(f.severity, 0)
    return sorted(findings, key=lambda f: f.score, reverse=True)


def save_findings(findings, output_path):
    """Write findings to JSON using dataclasses.asdict()."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump([dataclasses.asdict(f) for f in findings], fh, indent=2)
