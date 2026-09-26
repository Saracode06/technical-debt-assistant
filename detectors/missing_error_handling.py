import ast

from detectors.base_detector import Finding
from scanner.file_scanner import FileModel

_RISKY_CALLS = frozenset({'open', 'connect', 'execute', 'request'})


def _try_ancestors(node, parent_map):
    """Return True if any ancestor of node is a Try node."""
    current = parent_map.get(id(node))
    while current is not None:
        if isinstance(current, ast.Try):
            return True
        current = parent_map.get(id(current))
    return False


def detect(file_model: FileModel) -> list:
    # Build child -> parent map
    parent_map: dict = {}
    for node in ast.walk(file_model.tree):
        for child in ast.iter_child_nodes(node):
            parent_map[id(child)] = node

    findings = []
    for node in ast.walk(file_model.tree):
        if not isinstance(node, ast.Call):
            continue

        # Resolve the callable name
        func = node.func
        if isinstance(func, ast.Name):
            name = func.id
        elif isinstance(func, ast.Attribute):
            name = func.attr
        else:
            continue

        if name in _RISKY_CALLS and not _try_ancestors(node, parent_map):
            findings.append(Finding(
                file=str(file_model.path),
                line=node.lineno,
                category='missing_error_handling',
                severity='high',
                description=(
                    f"Call to '{name}()' at line {node.lineno} is not "
                    f"wrapped in a try/except block."
                ),
                suggestion=(
                    f"Wrap the '{name}()' call in a try/except to handle "
                    f"potential runtime errors gracefully."
                ),
            ))
    return findings
