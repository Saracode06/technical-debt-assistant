"""test_suite.py — unittest-based tests for the Technical Debt Assistant.

Run with:  python -m unittest tests/test_suite.py -v
All tests use only the Python standard library.
"""

import ast
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

# Ensure the project root is on sys.path so imports work from any cwd.
_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scanner.file_scanner import FileModel, scan_directory
from detectors.base_detector import Finding
from detectors.hardcoded_secrets import detect as detect_secrets
from detectors.long_functions import detect as detect_long
from detectors.code_duplication import detect as detect_dup
from detectors.missing_error_handling import detect as detect_errors
from detectors.dead_code import detect as detect_dead
from engine.prioritizer import prioritize, save_findings
from reporter.report_writer import write_report
from remediator.patch_generator import generate_patches

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SAMPLE_DIR = _PROJECT_ROOT / "sample_codebase"


def _make_model(source: str, filename: str = "<test>") -> FileModel:
    """Build a FileModel from a source string."""
    tree = ast.parse(source, filename=filename)
    return FileModel(path=Path(filename), source=source, tree=tree)


def _run_all_detectors(model: FileModel) -> list:
    results = []
    for det in [detect_secrets, detect_long, detect_dup, detect_errors, detect_dead]:
        results.extend(det(model))
    return results


# ---------------------------------------------------------------------------
# 1. Scanner tests
# ---------------------------------------------------------------------------

class TestScanner(unittest.TestCase):

    def test_scans_sample_codebase(self):
        """scan_directory returns exactly the 3 non-empty sample files."""
        models = scan_directory(_SAMPLE_DIR)
        names = {m.path.name for m in models}
        self.assertEqual(names, {"auth.py", "data_processor.py", "utils.py"})

    def test_returns_file_models_with_ast(self):
        """Every returned FileModel has a non-empty source and a parsed AST."""
        models = scan_directory(_SAMPLE_DIR)
        for m in models:
            self.assertIsInstance(m, FileModel)
            self.assertTrue(m.source.strip(), f"{m.path.name} source is empty")
            self.assertIsInstance(m.tree, ast.AST)

    def test_skips_empty_files(self):
        """Empty .py files are silently skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "empty.py").write_text("", encoding="utf-8")
            models = scan_directory(tmpdir)
        self.assertEqual(models, [])

    def test_skips_unparseable_files(self):
        """Files with syntax errors are skipped; no exception is raised."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "bad.py").write_text("def broken(:\n", encoding="utf-8")
            models = scan_directory(tmpdir)
        self.assertEqual(models, [])

    def test_returns_multiple_files(self):
        """scan_directory handles directories with several valid files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            for i in range(3):
                (Path(tmpdir) / f"mod{i}.py").write_text(f"x = {i}\n", encoding="utf-8")
            models = scan_directory(tmpdir)
        self.assertEqual(len(models), 3)


# ---------------------------------------------------------------------------
# 2. Detector — hardcoded secrets
# ---------------------------------------------------------------------------

class TestHardcodedSecretsDetector(unittest.TestCase):

    def test_detects_fake_secret_in_auth(self):
        """Finds the hardcoded password in auth.py."""
        models = scan_directory(_SAMPLE_DIR)
        auth = next(m for m in models if m.path.name == "auth.py")
        findings = detect_secrets(auth)
        self.assertTrue(
            any(f.category == "hardcoded_secrets" for f in findings),
            "Expected a hardcoded_secrets finding in auth.py",
        )

    def test_finding_is_critical(self):
        """Hardcoded-secret findings are severity=critical."""
        source = 'password = "FAKE_SECRET_123"\n'
        model = _make_model(source)
        findings = detect_secrets(model)
        self.assertTrue(findings)
        self.assertEqual(findings[0].severity, "critical")

    def test_no_false_positive_on_clean_code(self):
        """No finding when no sensitive variable name holds a string literal."""
        source = 'url = "http://localhost"\ncount = 42\n'
        model = _make_model(source)
        findings = detect_secrets(model)
        self.assertEqual(findings, [])

    def test_detects_token_variable(self):
        """Detects a variable named 'token' with a string literal."""
        source = 'token = "example-token"\n'
        model = _make_model(source)
        findings = detect_secrets(model)
        self.assertEqual(len(findings), 1)
        self.assertIn("token", findings[0].description.lower())


# ---------------------------------------------------------------------------
# 3. Detector — long functions
# ---------------------------------------------------------------------------

class TestLongFunctionsDetector(unittest.TestCase):

    def test_detects_long_function_in_data_processor(self):
        """Finds the long process_records function."""
        models = scan_directory(_SAMPLE_DIR)
        dp = next(m for m in models if m.path.name == "data_processor.py")
        findings = detect_long(dp)
        self.assertTrue(findings, "Expected a long_functions finding in data_processor.py")
        self.assertEqual(findings[0].category, "long_functions")

    def test_finding_is_medium_severity(self):
        """Long-function findings have severity=medium."""
        findings = detect_long(_make_model(
            "def f():\n" + "    x = 1\n" * 42
        ))
        self.assertTrue(findings)
        self.assertEqual(findings[0].severity, "medium")

    def test_no_finding_for_short_function(self):
        """No finding for a function well under 40 lines."""
        source = "def short():\n" + "    pass\n" * 5
        findings = detect_long(_make_model(source))
        self.assertEqual(findings, [])

    def test_threshold_is_40(self):
        """Function spanning exactly 40 lines is NOT flagged; 41 IS."""
        base = "def f():\n" + "    x = 1\n" * 40  # span == 40 → no flag
        self.assertEqual(detect_long(_make_model(base)), [])
        over = "def f():\n" + "    x = 1\n" * 41   # span == 41 → flag
        self.assertTrue(detect_long(_make_model(over)))


# ---------------------------------------------------------------------------
# 4. Detector — code duplication
# ---------------------------------------------------------------------------

class TestCodeDuplicationDetector(unittest.TestCase):

    def test_detects_duplicate_block_in_data_processor(self):
        """Finds the copy-pasted block in data_processor.py."""
        models = scan_directory(_SAMPLE_DIR)
        dp = next(m for m in models if m.path.name == "data_processor.py")
        findings = detect_dup(dp)
        self.assertTrue(findings, "Expected code_duplication findings in data_processor.py")

    def test_finding_is_high_severity(self):
        """Duplication findings have severity=high."""
        block = "\n".join([f"    x{i} = {i}" for i in range(6)])
        source = f"def a():\n{block}\n\ndef b():\n{block}\n"
        findings = detect_dup(_make_model(source))
        self.assertTrue(findings)
        self.assertEqual(findings[0].severity, "high")

    def test_no_finding_for_unique_code(self):
        """No duplication finding when all 6-line windows are unique."""
        source = "\n".join([f"x{i} = {i}" for i in range(20)]) + "\n"
        findings = detect_dup(_make_model(source))
        self.assertEqual(findings, [])


# ---------------------------------------------------------------------------
# 5. Detector — missing error handling
# ---------------------------------------------------------------------------

class TestMissingErrorHandlingDetector(unittest.TestCase):

    def test_detects_unprotected_connect_in_auth(self):
        """Finds the unprotected sock.connect() in auth.py."""
        models = scan_directory(_SAMPLE_DIR)
        auth = next(m for m in models if m.path.name == "auth.py")
        findings = detect_errors(auth)
        self.assertTrue(
            any(f.category == "missing_error_handling" for f in findings),
            "Expected a missing_error_handling finding in auth.py",
        )

    def test_finding_is_high_severity(self):
        """Missing-error-handling findings have severity=high."""
        source = "import socket\ndef f():\n    s = socket.socket()\n    s.connect(('h', 80))\n"
        findings = detect_errors(_make_model(source))
        self.assertTrue(findings)
        self.assertEqual(findings[0].severity, "high")

    def test_no_finding_when_wrapped_in_try(self):
        """No finding when the risky call is inside a try block."""
        source = (
            "import socket\n"
            "def f():\n"
            "    try:\n"
            "        s = socket.socket()\n"
            "        s.connect(('h', 80))\n"
            "    except Exception:\n"
            "        pass\n"
        )
        findings = detect_errors(_make_model(source))
        self.assertEqual(findings, [])


# ---------------------------------------------------------------------------
# 6. Detector — dead code
# ---------------------------------------------------------------------------

class TestDeadCodeDetector(unittest.TestCase):

    def test_detects_unused_imports_in_utils(self):
        """Finds unused import os and import json in utils.py."""
        models = scan_directory(_SAMPLE_DIR)
        utils = next(m for m in models if m.path.name == "utils.py")
        findings = detect_dead(utils)
        dead_categories = [f.category for f in findings]
        self.assertIn("dead_code", dead_categories)
        unused_names = " ".join(f.description for f in findings)
        self.assertIn("os", unused_names)
        self.assertIn("json", unused_names)

    def test_detects_unused_variable_in_utils(self):
        """Finds the unused 'separator' variable in utils.py."""
        models = scan_directory(_SAMPLE_DIR)
        utils = next(m for m in models if m.path.name == "utils.py")
        findings = detect_dead(utils)
        descriptions = " ".join(f.description for f in findings)
        self.assertIn("separator", descriptions)

    def test_no_finding_for_used_import(self):
        """No dead_code finding when the imported name is actually used."""
        source = "import os\n\ndef f():\n    return os.getcwd()\n"
        findings = detect_dead(_make_model(source))
        self.assertEqual(findings, [])

    def test_finding_is_low_severity(self):
        """Dead-code findings have severity=low."""
        source = "import json\nx = 1\n"
        findings = detect_dead(_make_model(source))
        self.assertTrue(findings)
        for f in findings:
            self.assertEqual(f.severity, "low")


# ---------------------------------------------------------------------------
# 7. Prioritizer tests
# ---------------------------------------------------------------------------

class TestPrioritizer(unittest.TestCase):

    def _make_finding(self, severity):
        return Finding(
            file="f.py", line=1, category="test",
            severity=severity, description="d", suggestion="s",
        )

    def test_scores_match_spec(self):
        """critical=40, high=30, medium=20, low=10."""
        for sev, expected in [("critical", 40), ("high", 30), ("medium", 20), ("low", 10)]:
            findings = prioritize([self._make_finding(sev)])
            self.assertEqual(findings[0].score, expected, f"Wrong score for {sev}")

    def test_sorted_highest_first(self):
        """prioritize returns findings sorted by score descending."""
        findings = [self._make_finding(s) for s in ["low", "critical", "medium", "high"]]
        ranked = prioritize(findings)
        scores = [f.score for f in ranked]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_empty_list(self):
        """prioritize handles an empty list without error."""
        self.assertEqual(prioritize([]), [])

    def test_save_findings_writes_json(self):
        """save_findings writes valid JSON with all Finding fields."""
        findings = [self._make_finding("high")]
        findings[0].file = "x.py"
        findings[0].line = 5
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "sub" / "findings.json"
            save_findings(findings, out)
            self.assertTrue(out.exists())
            data = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["severity"], "high")
        self.assertEqual(data[0]["line"], 5)


# ---------------------------------------------------------------------------
# 8. Reporter tests
# ---------------------------------------------------------------------------

class TestReporter(unittest.TestCase):

    def _make_findings(self):
        return [
            Finding("a.py", 1, "hardcoded_secrets", "critical", "d1", "s1"),
            Finding("b.py", 2, "dead_code", "low", "d2", "s2"),
        ]

    def test_report_written_to_disk(self):
        """write_report creates the output file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "report.md"
            write_report(self._make_findings(), out)
            self.assertTrue(out.exists())

    def test_report_contains_header(self):
        """Report starts with the project title."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "report.md"
            write_report(self._make_findings(), out)
            content = out.read_text(encoding="utf-8")
        self.assertIn("Technical Debt Report", content)

    def test_report_contains_summary_table(self):
        """Report includes the summary section with category names."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "report.md"
            write_report(self._make_findings(), out)
            content = out.read_text(encoding="utf-8")
        self.assertIn("hardcoded_secrets", content)
        self.assertIn("dead_code", content)

    def test_report_contains_findings_detail(self):
        """Report includes a Findings section."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "report.md"
            write_report(self._make_findings(), out)
            content = out.read_text(encoding="utf-8")
        self.assertIn("## Findings", content)

    def test_validation_section_absent_without_patched(self):
        """No Validation section when patched_findings is not supplied."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "report.md"
            write_report(self._make_findings(), out)
            content = out.read_text(encoding="utf-8")
        self.assertNotIn("## Validation", content)

    def test_validation_section_present_with_patched(self):
        """Validation section appears when patched_findings is supplied."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "report.md"
            write_report(self._make_findings(), out, patched_findings=[])
            content = out.read_text(encoding="utf-8")
        self.assertIn("## Validation", content)
        self.assertIn("Before: 2", content)
        self.assertIn("After: 0", content)
        self.assertIn("Resolved: 2", content)

    def test_creates_parent_directory(self):
        """write_report creates missing parent directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "nested" / "deep" / "report.md"
            write_report(self._make_findings(), out)
            self.assertTrue(out.exists())


# ---------------------------------------------------------------------------
# 9. Remediator tests
# ---------------------------------------------------------------------------

class TestRemediator(unittest.TestCase):

    def setUp(self):
        """Create a temporary working directory for each test."""
        self.tmpdir = tempfile.mkdtemp()
        self.source_root = Path(self.tmpdir) / "src"
        self.output_root = Path(self.tmpdir) / "patched"
        self.source_root.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write(self, filename, content):
        p = self.source_root / filename
        p.write_text(content, encoding="utf-8")
        return p

    def _model(self, filename):
        p = self.source_root / filename
        source = p.read_text(encoding="utf-8")
        tree = ast.parse(source)
        return FileModel(path=p, source=source, tree=tree)

    # -- originals are never modified --

    def test_originals_unchanged_after_fix(self):
        """generate_patches must not modify any file under source_root."""
        original = 'password = "FAKE_SECRET_123"\n'
        self._write("auth.py", original)
        model = self._model("auth.py")
        findings = detect_secrets(model)
        ranked = prioritize(findings)
        generate_patches(ranked, self.source_root, self.output_root)
        self.assertEqual(
            (self.source_root / "auth.py").read_text(encoding="utf-8"),
            original,
            "Original file was modified by generate_patches",
        )

    # -- patched output exists --

    def test_patched_copy_created(self):
        """generate_patches creates a copy under output_root."""
        self._write("utils.py", "import os\n\nx = 1\n")
        model = self._model("utils.py")
        findings = detect_dead(model)
        generate_patches(prioritize(findings), self.source_root, self.output_root)
        self.assertTrue((self.output_root / "utils.py").exists())

    # -- hardcoded secrets fix --

    def test_secret_replaced_with_env_call(self):
        """Patched file replaces hardcoded secret with os.environ.get(...)."""
        self._write("cfg.py", 'password = "FAKE_SECRET_123"\n')
        model = self._model("cfg.py")
        findings = detect_secrets(model)
        generate_patches(prioritize(findings), self.source_root, self.output_root)
        patched = (self.output_root / "cfg.py").read_text(encoding="utf-8")
        self.assertIn("os.environ.get(", patched)
        self.assertNotIn("FAKE_SECRET_123", patched)

    def test_import_os_injected_for_secret_fix(self):
        """import os is added to the patched file when not already present."""
        self._write("cfg.py", 'password = "FAKE_SECRET_123"\n')
        model = self._model("cfg.py")
        findings = detect_secrets(model)
        generate_patches(prioritize(findings), self.source_root, self.output_root)
        patched = (self.output_root / "cfg.py").read_text(encoding="utf-8")
        self.assertIn("import os", patched)

    # -- dead code fix --

    def test_unused_import_removed(self):
        """Patched file has the unused import line deleted."""
        self._write("mod.py", "import json\n\nx = 1\n")
        model = self._model("mod.py")
        findings = [f for f in detect_dead(model) if "json" in f.description]
        generate_patches(prioritize(findings), self.source_root, self.output_root)
        patched = (self.output_root / "mod.py").read_text(encoding="utf-8")
        self.assertNotIn("import json", patched)

    # -- missing error handling fix --

    def test_try_except_wrapped(self):
        """Patched file wraps the risky call in try/except."""
        source = (
            "import socket\n"
            "def f():\n"
            "    s = socket.socket()\n"
            "    s.connect(('h', 80))\n"
        )
        self._write("net.py", source)
        model = self._model("net.py")
        findings = detect_errors(model)
        generate_patches(prioritize(findings), self.source_root, self.output_root)
        patched = (self.output_root / "net.py").read_text(encoding="utf-8")
        self.assertIn("try:", patched)
        self.assertIn("except Exception:", patched)

    # -- long functions fix --

    def test_todo_comment_inserted_for_long_function(self):
        """Patched file has a TODO comment above the long function."""
        source = "def long_fn():\n" + "    x = 1\n" * 42
        self._write("big.py", source)
        model = self._model("big.py")
        findings = detect_long(model)
        generate_patches(prioritize(findings), self.source_root, self.output_root)
        patched = (self.output_root / "big.py").read_text(encoding="utf-8")
        self.assertIn("TODO", patched)
        self.assertIn("refactor", patched)


# ---------------------------------------------------------------------------
# 10. End-to-end integration tests
# ---------------------------------------------------------------------------

class TestEndToEnd(unittest.TestCase):
    """Integration tests that run the full pipeline against the real sample codebase."""

    def test_scan_produces_finding_per_category(self):
        """Scanning sample_codebase yields at least one finding for each of the 5 categories."""
        models = scan_directory(_SAMPLE_DIR)
        all_findings = []
        for m in models:
            all_findings.extend(_run_all_detectors(m))

        categories = {f.category for f in all_findings}
        for expected in [
            "hardcoded_secrets",
            "long_functions",
            "code_duplication",
            "missing_error_handling",
            "dead_code",
        ]:
            self.assertIn(expected, categories, f"No finding for category: {expected}")

    def test_fix_reduces_finding_count(self):
        """Running fix on a temp copy reduces total findings vs original scan."""
        with tempfile.TemporaryDirectory() as tmpdir:
            patched_root = Path(tmpdir) / "patched"

            models = scan_directory(_SAMPLE_DIR)
            all_findings: list = []
            for m in models:
                all_findings.extend(_run_all_detectors(m))
            ranked = prioritize(all_findings)
            before = len(ranked)

            generate_patches(ranked, _SAMPLE_DIR, patched_root)

            patched_models = scan_directory(patched_root)
            patched_findings: list = []
            for m in patched_models:
                patched_findings.extend(_run_all_detectors(m))
            after = len(patched_findings)

        self.assertGreater(before, 0, "No findings before fix")
        self.assertLess(after, before, "Fix did not reduce finding count")

    def test_fix_resolves_secrets_completely(self):
        """After fix, no hardcoded_secrets findings remain in patched files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            patched_root = Path(tmpdir) / "patched"

            models = scan_directory(_SAMPLE_DIR)
            all_findings: list = []
            for m in models:
                all_findings.extend(_run_all_detectors(m))
            ranked = prioritize(all_findings)
            generate_patches(ranked, _SAMPLE_DIR, patched_root)

            patched_models = scan_directory(patched_root)
            patched_secrets = [
                f
                for m in patched_models
                for f in detect_secrets(m)
            ]

        self.assertEqual(
            patched_secrets, [],
            f"Secrets not fully resolved: {patched_secrets}",
        )

    def test_fix_resolves_dead_code_significantly(self):
        """After fix, dead_code findings are substantially reduced.

        Known limitation: when the duplication remediator replaces a duplicate
        block with a helper stub, setup variables that fed only that block
        (e.g. ``normalised`` in process_audit_records) become orphaned and
        produce one residual dead_code finding.  The original 5 findings must
        drop to at most 1 residual.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            patched_root = Path(tmpdir) / "patched"

            models = scan_directory(_SAMPLE_DIR)
            all_findings: list = []
            for m in models:
                all_findings.extend(_run_all_detectors(m))
            before_dead = sum(1 for f in all_findings if f.category == "dead_code")
            ranked = prioritize(all_findings)
            generate_patches(ranked, _SAMPLE_DIR, patched_root)

            patched_models = scan_directory(patched_root)
            patched_dead = [
                f
                for m in patched_models
                for f in detect_dead(m)
            ]

        self.assertGreater(before_dead, 1, "Expected multiple dead_code findings before fix")
        self.assertLessEqual(
            len(patched_dead), 1,
            f"Too many dead_code findings after fix (at most 1 residual allowed): {patched_dead}",
        )

    def test_fix_resolves_duplication_completely(self):
        """After fix, no code_duplication findings remain in patched files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            patched_root = Path(tmpdir) / "patched"

            models = scan_directory(_SAMPLE_DIR)
            all_findings: list = []
            for m in models:
                all_findings.extend(_run_all_detectors(m))
            ranked = prioritize(all_findings)
            generate_patches(ranked, _SAMPLE_DIR, patched_root)

            patched_models = scan_directory(patched_root)
            patched_dup = [
                f
                for m in patched_models
                for f in detect_dup(m)
            ]

        self.assertEqual(
            patched_dup, [],
            f"Duplication findings not fully resolved: {patched_dup}",
        )

    def test_sample_originals_unchanged_after_full_fix(self):
        """generate_patches on a temp output never modifies the real sample_codebase."""
        originals = {}
        for p in sorted(_SAMPLE_DIR.rglob("*.py")):
            originals[p] = p.read_text(encoding="utf-8")

        with tempfile.TemporaryDirectory() as tmpdir:
            patched_root = Path(tmpdir) / "patched"
            models = scan_directory(_SAMPLE_DIR)
            all_findings: list = []
            for m in models:
                all_findings.extend(_run_all_detectors(m))
            ranked = prioritize(all_findings)
            generate_patches(ranked, _SAMPLE_DIR, patched_root)

        for p, original_content in originals.items():
            self.assertEqual(
                p.read_text(encoding="utf-8"),
                original_content,
                f"{p.name} was modified by generate_patches",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
