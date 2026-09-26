import re

from detectors.base_detector import Finding
from scanner.file_scanner import FileModel

_WINDOW = 6
# Strip inline comments and normalise whitespace before hashing
_COMMENT = re.compile(r'\s*#.*$')


def _normalise(line: str) -> str:
    return _COMMENT.sub('', line).strip()


def detect(file_model: FileModel) -> list:
    lines = file_model.source.splitlines()
    if len(lines) < _WINDOW:
        return []

    # Build normalised windows and record first occurrence line numbers
    seen: dict = {}   # hash -> first start line (1-based)
    reported: set = set()
    findings = []

    for i in range(len(lines) - _WINDOW + 1):
        window = [_normalise(lines[i + j]) for j in range(_WINDOW)]
        # Skip windows that are mostly blank
        if sum(1 for w in window if w) < 3:
            continue
        key = hash(tuple(window))
        if key in seen:
            if key not in reported:
                reported.add(key)
                findings.append(Finding(
                    file=str(file_model.path),
                    line=i + 1,  # 1-based line of second occurrence
                    category='code_duplication',
                    severity='high',
                    description=(
                        f"Duplicate {_WINDOW}-line block detected "
                        f"(first seen at line {seen[key]}, repeated at line {i + 1})."
                    ),
                    suggestion=(
                        "Extract the repeated block into a shared helper function."
                    ),
                ))
        else:
            seen[key] = i + 1  # 1-based

    return findings
