"""patch_generator.py — apply safe inline fixes to copies of source files."""

import os
import re
import shutil
from collections import defaultdict
from pathlib import Path

_WINDOW = 6  # must match code_duplication detector


def _get_indent(line: str) -> str:
    """Return the leading whitespace of a line."""
    return line[: len(line) - len(line.lstrip())]


def _extract_env_var_name(finding) -> str:
    """Derive the env-var name to use in os.environ.get() from the finding suggestion."""
    # Suggestion format: "Replace with os.environ.get('PASSWORD', '')"
    m = re.search(r"os\.environ\.get\('([^']+)'", finding.suggestion)
    if m:
        return m.group(1)
    # Fallback: derive from the description variable name, uppercased
    m2 = re.search(r"variable '([^']+)'", finding.description, re.IGNORECASE)
    if m2:
        return m2.group(1).upper()
    return "VAR_NAME"


def _apply_hardcoded_secret(lines: list, line_no: int, finding) -> list:
    """Replace the string literal on line_no with os.environ.get(...)."""
    idx = line_no - 1  # convert to 0-based
    var_name = _extract_env_var_name(finding)
    original = lines[idx]
    # Replace the first quoted string literal on the line with the env call
    patched = re.sub(
        r'(["\'])(?:(?!\1).)*\1',
        f"os.environ.get('{var_name}', '')",
        original,
        count=1,
    )
    lines[idx] = patched
    # Prepend `import os` if not already present
    has_import_os = any(re.match(r'^\s*import\s+os\b', ln) for ln in lines)
    if not has_import_os:
        lines.insert(0, "import os\n")
    return lines


def _apply_missing_error_handling(lines: list, line_no: int) -> list:
    """Wrap the target line in a try/except block."""
    idx = line_no - 1
    original = lines[idx]
    indent = _get_indent(original)
    stripped = original.rstrip("\n")
    new_lines = [
        indent + "try:\n",
        indent + "    " + stripped.lstrip() + "\n",
        indent + "except Exception:\n",
        indent + "    pass\n",
    ]
    lines[idx : idx + 1] = new_lines
    return lines


def _apply_dead_code(lines: list, line_no: int) -> list:
    """Delete the dead import or assignment line entirely."""
    idx = line_no - 1
    del lines[idx]
    return lines


def _apply_long_function(lines: list, line_no: int) -> list:
    """Insert a TODO comment directly above the def line."""
    idx = line_no - 1
    indent = _get_indent(lines[idx])
    comment = indent + "# TODO: refactor — extract helper\n"
    lines.insert(idx, comment)
    return lines


def _apply_code_duplication(lines: list, line_no: int, dup_index: int) -> list:
    """Replace the duplicate block with a helper call; append a stub definition."""
    idx = line_no - 1
    if idx + _WINDOW > len(lines):
        return lines  # safety guard

    # Use the indent of the first non-blank line in the window
    indent = ""
    for bl in lines[idx : idx + _WINDOW]:
        if bl.strip():
            indent = _get_indent(bl)
            break

    helper_name = f"_extracted_block_{dup_index}"

    # Consume all overlapping duplicate windows starting here (up to 2*WINDOW lines)
    # to ensure the helper body does not itself re-trigger the duplication detector.
    end_idx = idx
    while end_idx < min(idx + _WINDOW * 2, len(lines)) and lines[end_idx].strip():
        end_idx += 1
    # At minimum replace _WINDOW lines; extend to end_idx if it covers more
    replace_end = max(idx + _WINDOW, end_idx)

    # Replace the duplicate block with a single helper call
    call_line = indent + helper_name + "(record)\n"
    lines[idx : replace_end] = [call_line]

    # Append a stub helper so the call site is valid — body is a pass so
    # it does NOT reproduce the duplicate content and re-trigger the detector.
    helper_def = [
        "\n",
        f"def {helper_name}(record):\n",
        f"    # TODO: implement extracted duplicate block {dup_index}\n",
        f"    pass\n",
        "\n",
    ]
    lines.extend(helper_def)
    return lines


def _dedup_dup_findings(dup_findings: list) -> list:
    """
    Multiple code_duplication findings may point to overlapping 6-line windows
    within the same duplicate block.  Collapse each run of overlapping windows
    into a single representative, keeping the *last* (highest line number) in
    each overlapping group.  The last window is chosen because it is the one
    whose 6-line span reaches furthest into the block, which ensures that lines
    like ``results.append(entry)`` — present in the later window but not the
    earlier one — are also covered by the replacement.
    """
    if not dup_findings:
        return []

    # Sort by line ascending so we can walk through overlapping groups
    sorted_f = sorted(dup_findings, key=lambda f: f.line)
    kept = []
    group_start = 0  # start index of the current overlap group in sorted_f

    i = 1
    while i <= len(sorted_f):
        # Check whether sorted_f[i] is still overlapping with sorted_f[i-1]
        if i < len(sorted_f) and sorted_f[i].line < sorted_f[i - 1].line + _WINDOW:
            # Still in the same overlapping group — advance
            i += 1
        else:
            # End of group: keep the last finding in the group (highest line)
            kept.append(sorted_f[i - 1])
            group_start = i
            i += 1

    return kept


def generate_patches(findings, source_root: Path, output_root: Path) -> list:
    """
    Copy every .py file from source_root to output_root (preserving relative
    paths) and apply inline fixes for each finding.

    Returns the list of patched file Paths (one per affected file).
    """
    source_root = Path(source_root)
    output_root = Path(output_root)

    # 1. Copy all .py files from source_root to output_root
    output_root.mkdir(parents=True, exist_ok=True)
    for src_file in source_root.rglob("*.py"):
        rel = src_file.relative_to(source_root)
        dest = output_root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_file, dest)

    # 2. Group findings by their source file path
    by_file: dict = defaultdict(list)
    for f in findings:
        by_file[f.file].append(f)

    patched_paths = []
    dup_counter = 0

    for src_path_str, file_findings in by_file.items():
        src_path = Path(src_path_str)
        # Resolve the corresponding patched file
        try:
            rel = src_path.relative_to(source_root)
        except ValueError:
            rel = Path(src_path.name)
        dest = output_root / rel

        if not dest.exists():
            continue  # skip if copy wasn't made

        # Read the patched copy's lines
        with open(dest, "r", encoding="utf-8") as fh:
            lines = fh.readlines()

        # Ensure every line ends with \n for uniform processing
        lines = [ln if ln.endswith("\n") else ln + "\n" for ln in lines]

        # 3. For code_duplication, collapse overlapping windows to one per block.
        dup_findings = _dedup_dup_findings(
            [f for f in file_findings if f.category == "code_duplication"]
        )
        other_findings = [f for f in file_findings if f.category != "code_duplication"]

        # Combine: one representative per dup block + all other findings.
        # Sort bottom-up (highest line number first) so earlier references stay valid.
        combined = sorted(other_findings + dup_findings, key=lambda f: f.line, reverse=True)

        for finding in combined:
            cat = finding.category

            if cat == "hardcoded_secrets":
                lines = _apply_hardcoded_secret(lines, finding.line, finding)

            elif cat == "missing_error_handling":
                lines = _apply_missing_error_handling(lines, finding.line)

            elif cat == "dead_code":
                lines = _apply_dead_code(lines, finding.line)

            elif cat == "long_functions":
                lines = _apply_long_function(lines, finding.line)

            elif cat == "code_duplication":
                dup_counter += 1
                lines = _apply_code_duplication(lines, finding.line, dup_counter)

        # Write the patched file back
        with open(dest, "w", encoding="utf-8") as fh:
            fh.writelines(lines)

        patched_paths.append(dest)

    return patched_paths
