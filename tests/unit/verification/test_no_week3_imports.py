"""Unit test verifying that gateway and verification packages are self-contained and have no Week 3 dependencies."""

import ast
from pathlib import Path


def test_no_week3_imports_or_references():
    repo_root = Path(__file__).resolve().parents[3]
    targets = [
        repo_root / "src" / "project_sentinel" / "gateway",
        repo_root / "src" / "project_sentinel" / "verification",
    ]

    forbidden_modules = {"project_sentinel.analysis", "project_sentinel.models"}
    forbidden_tokens = [
        "SecurityAnalysisRecord",
        "artifacts/analysis",
        "security-analysis",
        "AnalysisPacket",
        "group_key",
    ]

    for target_dir in targets:
        for py_file in target_dir.glob("*.py"):
            content = py_file.read_text(encoding="utf-8")

            # Check string tokens
            for token in forbidden_tokens:
                assert token not in content, f"Forbidden token {token!r} found in {py_file}"

            # Check AST imports
            tree = ast.parse(content, filename=str(py_file))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        for forbidden in forbidden_modules:
                            assert not alias.name.startswith(forbidden), (
                                f"Forbidden import '{alias.name}' in {py_file}"
                            )
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    for forbidden in forbidden_modules:
                        assert not module.startswith(forbidden), (
                            f"Forbidden from-import '{module}' in {py_file}"
                        )
