"""Package verification cũ phải biến mất hoàn toàn."""

import importlib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_verification_package_is_gone():
    assert not (REPO_ROOT / "src" / "project_sentinel" / "verification").exists()


def test_verification_package_is_not_importable():
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("project_sentinel.verification")


def test_dead_configs_and_schemas_are_gone():
    for relative in [
        "configs/verification/endpoint-catalog.json",
        "configs/verification/probe-objectives.json",
        "configs/verification/probe-templates.json",
        "schemas/probe-proposal.schema.json",
        "schemas/verification-plan.schema.json",
        "FOLDER_STRUCTURE_REFACTOR_GUIDE.md",
    ]:
        assert not (REPO_ROOT / relative).exists(), f"Còn sót: {relative}"


def test_no_source_file_mentions_a_week_number():
    offenders = []
    for path in (REPO_ROOT / "src").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for token in ("Week 3", "Week 4", "week3", "week4"):
            if token in text:
                offenders.append(f"{path.relative_to(REPO_ROOT)}: {token}")
    assert not offenders, "Số tuần không được xuất hiện trong code production:\n" + "\n".join(offenders)
