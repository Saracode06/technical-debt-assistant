import ast
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class FileModel:
    path: Path
    source: str
    tree: ast.AST


def scan_directory(path) -> list:
    """Walk *path* recursively, parse every *.py file, return a list of FileModel objects.

    Files that fail ast.parse() are skipped with a warning written to stderr.
    """
    root = Path(path)
    models = []

    for py_file in sorted(root.rglob("*.py")):
        source = py_file.read_text(encoding="utf-8")

        # Skip completely empty files — nothing to analyse
        if not source.strip():
            continue

        try:
            tree = ast.parse(source, filename=str(py_file))
        except SyntaxError as exc:
            print(f"WARNING: skipping {py_file} — parse error: {exc}", file=sys.stderr)
            continue

        models.append(FileModel(path=py_file, source=source, tree=tree))

    return models
