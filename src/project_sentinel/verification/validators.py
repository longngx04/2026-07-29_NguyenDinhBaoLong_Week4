"""
JSON Schema validation functions for VerificationPlan and VerificationResult.
"""

import json
from pathlib import Path
from typing import Any, Dict, Union
import jsonschema

_CURRENT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _CURRENT_DIR.parents[2]
DEFAULT_PLAN_SCHEMA_PATH = _REPO_ROOT / "schemas" / "verification-plan.schema.json"
DEFAULT_RESULT_SCHEMA_PATH = _REPO_ROOT / "schemas" / "verification-result.schema.json"


def _load_schema(schema_path: Union[str, Path]) -> Dict[str, Any]:
    path = Path(schema_path)
    if not path.exists():
        rel_path = Path.cwd() / schema_path
        if rel_path.exists():
            path = rel_path
        else:
            raise FileNotFoundError(f"Schema file not found: {schema_path}")
    return json.loads(path.read_text(encoding="utf-8"))


def validate_verification_plan_schema(
    data: Dict[str, Any],
    schema_path: Union[str, Path] = DEFAULT_PLAN_SCHEMA_PATH
) -> None:
    """
    Validate a verification plan dictionary against verification-plan.schema.json.
    Raises jsonschema.ValidationError if invalid.
    """
    schema = _load_schema(schema_path)
    jsonschema.validate(instance=data, schema=schema)


def validate_verification_result_schema(
    data: Dict[str, Any],
    schema_path: Union[str, Path] = DEFAULT_RESULT_SCHEMA_PATH
) -> None:
    """
    Validate a verification result dictionary against verification-result.schema.json.
    Raises jsonschema.ValidationError if invalid.
    """
    schema = _load_schema(schema_path)
    jsonschema.validate(instance=data, schema=schema)
