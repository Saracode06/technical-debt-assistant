import ast

from detectors.base_detector import Finding
from scanner.file_scanner import FileModel


def detect(file_model: FileModel) -> list:
    findings = []
    tree = file_model.tree
    src = str(file_model.path)

    # Collect all Name nodes used in Load context
    load_names: set = {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
    }

    # --- Unused imports ---
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                bound = alias.asname if alias.asname else alias.name.split('.')[0]
                if bound not in load_names:
                    findings.append(Finding(
                        file=src,
                        line=node.lineno,
                        category='dead_code',
                        severity='low',
                        description=f"Imported name '{bound}' is never used.",
                        suggestion=f"Remove the unused 'import {alias.name}' statement.",
                    ))
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                bound = alias.asname if alias.asname else alias.name
                if bound not in load_names:
                    findings.append(Finding(
                        file=src,
                        line=node.lineno,
                        category='dead_code',
                        severity='low',
                        description=f"Imported name '{bound}' is never used.",
                        suggestion=f"Remove the unused 'from ... import {alias.name}' statement.",
                    ))

    # --- Unused assigned variables ---
    # Count Store and Load occurrences per name within function scopes
    for func_node in ast.walk(tree):
        if not isinstance(func_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        store_lines: dict = {}
        local_loads: set = set()
        for node in ast.walk(func_node):
            if isinstance(node, ast.Name):
                if isinstance(node.ctx, ast.Store):
                    # Record first assignment line only
                    if node.id not in store_lines:
                        store_lines[node.id] = node.lineno
                elif isinstance(node.ctx, ast.Load):
                    local_loads.add(node.id)
        for name, lineno in store_lines.items():
            if name not in local_loads:
                findings.append(Finding(
                    file=src,
                    line=lineno,
                    category='dead_code',
                    severity='low',
                    description=f"Variable '{name}' is assigned but never read.",
                    suggestion=f"Remove the unused assignment of '{name}'.",
                ))

    return findings
