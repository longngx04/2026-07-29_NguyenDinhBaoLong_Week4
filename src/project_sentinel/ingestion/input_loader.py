"""
Input loader and validator for normalized findings JSON files.
"""

import json
from pathlib import Path
from typing import Union
from project_sentinel.models import NormalizedFinding, NormalizedFindingFile


def load_findings(path: Union[str, Path]) -> NormalizedFindingFile:
    """Load and validate normalized findings from a JSON file.
    
    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If JSON is malformed or missing required schema fields.
    """
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Input file not found: {file_path}")

    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in input file {file_path}: {e}") from e

    if not isinstance(data, dict):
        raise ValueError("Input findings root must be a JSON object")

    if "findings" not in data or not isinstance(data["findings"], list):
        raise ValueError("Input JSON must contain a 'findings' array")

    findings = []
    for idx, item in enumerate(data["findings"]):
        if not isinstance(item, dict):
            raise ValueError(f"Finding item at index {idx} is not an object")
        
        # Check required finding fields
        missing = [f for f in ["id", "rule_id"] if f not in item]
        if missing:
            raise ValueError(f"Finding at index {idx} missing required fields: {missing}")

        if not str(item.get("id", "")).strip():
            raise ValueError(f"Finding at index {idx} has empty id")
        if not str(item.get("rule_id", "")).strip():
            raise ValueError(f"Finding at index {idx} has empty rule_id")

        loc = item.get("location")
        if isinstance(loc, dict):
            if "file" not in loc or "line" not in loc:
                raise ValueError(f"Finding at index {idx} has invalid location dict: {loc}")
        else:
            if "file_or_url" not in item and "file" not in item:
                raise ValueError(f"Finding at index {idx} missing location/file_or_url/file field")
            if "line" not in item:
                raise ValueError(f"Finding at index {idx} missing line field")

        findings.append(NormalizedFinding.from_dict(item))

    count = data.get("count", len(findings))
    return NormalizedFindingFile(count=count, findings=findings)
