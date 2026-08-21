"""
JSON/JSONL utilities, JSON Schema validation, and Provenance validation.
"""

import json
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import jsonschema


def write_jsonl_atomic(records: List[Dict[str, Any]], output_path: Union[str, Path]) -> None:
    """Write records to a JSONL file atomically using a temporary file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False, encoding="utf-8") as tf:
        temp_name = tf.name
        for rec in records:
            tf.write(json.dumps(rec, ensure_ascii=False) + "\n")
    
    Path(temp_name).replace(path)


def read_jsonl(input_path: Union[str, Path]) -> List[Dict[str, Any]]:
    """Read a JSONL file and return a list of dictionary records."""
    path = Path(input_path)
    if not path.exists():
        raise FileNotFoundError(f"JSONL file not found: {path}")

    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON at line {line_num} in {path}: {e}") from e
    return records


def validate_record_schema(
    record_dict: Dict[str, Any],
    schema_path: Union[str, Path]
) -> Tuple[bool, Optional[str]]:
    """Validate a single record dictionary against the JSON schema.
    
    Returns:
        (True, None) if valid, or (False, error_message) if invalid.
    """
    path = Path(schema_path)
    if not path.exists():
        return False, f"Schema file not found: {path}"

    try:
        schema = json.loads(path.read_text(encoding="utf-8"))
        jsonschema.validate(instance=record_dict, schema=schema)
        return True, None
    except jsonschema.ValidationError as e:
        return False, f"Schema validation error: {e.message} at path {list(e.path)}"
    except Exception as e:
        return False, f"Unexpected error during schema validation: {e}"


def validate_provenance(
    record_dict: Dict[str, Any],
    input_group_finding_ids: List[str],
    input_locations: List[Dict[str, Any]],
    input_knowledge_paths: List[str],
    input_cwes: Optional[List[str]] = None,
    input_owasps: Optional[List[str]] = None,
    input_source_evidence: Optional[List[Dict[str, Any]]] = None
) -> Tuple[bool, List[str]]:
    """Validate provenance of LLM output against supplied input packet data.
    
    Returns:
        (is_valid, list_of_errors)
    """
    errors: List[str] = []

    # 1. source_finding_ids must be subset of input_group_finding_ids
    rec_ids = record_dict.get("source_finding_ids", [])
    for fid in rec_ids:
        if fid not in input_group_finding_ids:
            errors.append(f"Invented source_finding_id '{fid}' not present in input group")

    # 2. locations must exist in input_locations
    input_loc_tuples = {(loc["file"], loc["line"]) for loc in input_locations if "file" in loc and "line" in loc}
    rec_locs = record_dict.get("locations", [])
    for loc in rec_locs:
        loc_tuple = (loc.get("file"), loc.get("line"))
        if loc_tuple not in input_loc_tuples:
            errors.append(f"Invented location '{loc_tuple}' not present in input group")

    # 3. knowledge_refs must exist in input_knowledge_paths
    rec_k_refs = record_dict.get("knowledge_refs", [])
    for kref in rec_k_refs:
        kpath = kref.get("path")
        if kpath not in input_knowledge_paths:
            errors.append(f"Invented knowledge_ref path '{kpath}' not in retrieved hits")

    # 4. cwe must be subset of input_cwes (empty input = only [] valid)
    valid_cwes = set(input_cwes or [])
    for cwe in record_dict.get("cwe", []):
        if cwe not in valid_cwes:
            errors.append(f"Invented CWE '{cwe}' not present in input group")

    # 5. owasp must be subset of input_owasps (empty input = only [] valid)
    valid_owasps = set(input_owasps or [])
    for owasp in record_dict.get("owasp", []):
        if owasp not in valid_owasps:
            errors.append(f"Invented OWASP '{owasp}' not present in input group")

    # 6. source evidence refs must match input_source_evidence paths
    valid_ev_paths = {ev.get("path") for ev in (input_source_evidence or []) if ev.get("path")}
    for ev in record_dict.get("evidence", []):
        if ev.get("type") == "source":
            ev_path = ev.get("path")
            if not ev_path or ev_path not in valid_ev_paths:
                errors.append(f"Invented source evidence path '{ev_path}' not present in input evidence")

    return len(errors) == 0, errors
