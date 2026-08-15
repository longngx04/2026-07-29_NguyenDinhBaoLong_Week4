"""Guard test: no test doubles (Fake/Mock/Stub/Dummy) exist in src/ or tests/.

Settled decision D9 — this repository contains no fake, mock, or stub
implementation.  This test uses AST inspection to fail if a class whose name
starts with Fake, Mock, Stub, or Dummy appears anywhere under src/ or tests/.
"""

import ast
import pathlib
import re

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SEARCH_DIRS = [REPO_ROOT / "src", REPO_ROOT / "tests"]
FORBIDDEN_PREFIXES = ("Fake", "Mock", "Stub", "Dummy")

# Also catch provider=="fake" string literals
FORBIDDEN_PATTERNS = [
    re.compile(r"""provider.*["']fake["']"""),
    re.compile(r"""LLM_PROVIDER\s*=\s*["']?fake["']?"""),
]

SELF_PATH = pathlib.Path(__file__).resolve()


def _collect_python_files():
    files = []
    for d in SEARCH_DIRS:
        if d.is_dir():
            for f in d.rglob("*.py"):
                if f.resolve() != SELF_PATH:
                    files.append(f)
    return files


def _find_forbidden_classes(filepath: pathlib.Path):
    """Return list of (line, class_name) for forbidden class definitions."""
    try:
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(filepath))
    except (SyntaxError, UnicodeDecodeError):
        return []

    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            if node.name.startswith(FORBIDDEN_PREFIXES):
                violations.append((node.lineno, node.name))
    return violations


def _find_forbidden_patterns(filepath: pathlib.Path):
    """Return list of (line_no, line_text) matching forbidden string patterns."""
    try:
        lines = filepath.read_text(encoding="utf-8").splitlines()
    except (UnicodeDecodeError, OSError):
        return []

    violations = []
    for i, line in enumerate(lines, 1):
        for pattern in FORBIDDEN_PATTERNS:
            if pattern.search(line):
                violations.append((i, line.strip()))
                break
    return violations


def test_no_double_classes():
    """No class named Fake*/Mock*/Stub*/Dummy* exists under src/ or tests/."""
    all_violations = []
    for py_file in _collect_python_files():
        for lineno, class_name in _find_forbidden_classes(py_file):
            rel = py_file.relative_to(REPO_ROOT)
            all_violations.append(f"  {rel}:{lineno} — class {class_name}")

    assert not all_violations, (
        "Forbidden test-double classes found (D9):\n"
        + "\n".join(all_violations)
    )


def test_no_fake_provider_references():
    """No provider='fake' or LLM_PROVIDER=fake pattern exists under src/ or tests/."""
    all_violations = []
    for py_file in _collect_python_files():
        for lineno, line_text in _find_forbidden_patterns(py_file):
            rel = py_file.relative_to(REPO_ROOT)
            all_violations.append(f"  {rel}:{lineno} — {line_text}")

    assert not all_violations, (
        "Forbidden fake-provider references found (D9):\n"
        + "\n".join(all_violations)
    )
