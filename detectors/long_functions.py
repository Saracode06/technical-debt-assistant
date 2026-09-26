import ast

from detectors.base_detector import Finding
from scanner.file_scanner import FileModel

_THRESHOLD = 40


def detect(file_model: FileModel) -> list:
    findings = []
    for node in ast.walk(file_model.tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # end_lineno is available in Python 3.8+
            span = node.end_lineno - node.lineno
            if span > _THRESHOLD:
                findings.append(Finding(
                    file=str(file_model.path),
                    line=node.lineno,
                    category='long_functions',
                    severity='medium',
                    description=(
                        f"Function '{node.name}' spans {span} lines "
                        f"(threshold: {_THRESHOLD})."
                    ),
                    suggestion=(
                        "Break the function into smaller, single-responsibility helpers."
                    ),
                ))
    return findings
