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


def _normalise_evidence_content(value: Any) -> str:
    """Bo lop boc untrusted va khoang trang thua truoc khi so sanh bang chung.

    Agent nhan evidence da boc trong the `<untrusted_app_response>`, nen no echo
    lai ban boc. So sanh nguyen van voi ban chua boc se danh truot moi record hop
    le — mot luat provenance ban nham la mot luat lam mat toan bo ket qua.
    """
    if not isinstance(value, str):
        return ""
    text = value.strip()
    for tag in ("<untrusted_app_response>", "</untrusted_app_response>"):
        text = text.replace(tag, "")
    return "\n".join(line.rstrip() for line in text.strip().splitlines())


def validate_provenance(
    record_dict: Dict[str, Any],
    input_group_finding_ids: List[str],
    input_locations: List[Dict[str, Any]],
    input_knowledge_paths: List[str],
    input_cwes: Optional[List[str]] = None,
    input_owasps: Optional[List[str]] = None,
    input_source_evidence: Optional[List[Dict[str, Any]]] = None,
    input_group_key: Optional[str] = None,
    input_knowledge_hits: Optional[List[Dict[str, Any]]] = None,
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

    # 7. group_key phai khop chinh xac. Nhom la quyet dinh cua he thong, khong
    #    phai thu Agent duoc dat lai ten.
    if input_group_key is not None and record_dict.get("group_key") != input_group_key:
        errors.append(
            f"group_key '{record_dict.get('group_key')}' khong khop input "
            f"'{input_group_key}'"
        )

    # 8. Noi dung bang chung phai khop NGUYEN VAN, khong chi khop duong dan.
    #    Day la ke ho nguy hiem nhat cua validator cu: mot record co the dung
    #    duong dan that va dong that roi bia ra doan ma tai vi tri do, va van qua
    #    duoc ca ba lop. Nguoi doc se tin doan ma duoc trich la that.
    if input_source_evidence:
        # Agent nhin thay evidence DA BOC trong the <untrusted_app_response>
        # (xem `llm/base.build_packet_dict`), nen no echo lai ban boc. So sanh
        # nguyen van voi ban chua boc se lam MOI record hop le bi danh truot.
        # Chuan hoa hai dau ve cung mot dang truoc khi so.
        by_path: Dict[str, List[Dict[str, Any]]] = {}
        for item in input_source_evidence:
            path_value = item.get("path")
            if isinstance(path_value, str):
                by_path.setdefault(path_value, []).append(item)

        for ev in record_dict.get("evidence", []):
            if not isinstance(ev, dict) or ev.get("type") != "source":
                continue
            ev_path = ev.get("path")
            candidates = by_path.get(ev_path, []) if isinstance(ev_path, str) else []
            if not candidates:
                continue  # da bao o luat 6
            if not any(
                _normalise_evidence_content(ev.get("content"))
                == _normalise_evidence_content(candidate.get("content"))
                and ev.get("start_line") == candidate.get("start_line")
                and ev.get("end_line") == candidate.get("end_line")
                for candidate in candidates
            ):
                errors.append(
                    f"Source evidence cho '{ev_path}' khong khop input: "
                    f"content/start_line/end_line da bi doi hoac bia ra"
                )

    # 9. Diem lien quan cua knowledge la so do he thong tinh, khong phai thu
    #    Agent duoc dat.
    if input_knowledge_hits:
        scores = {
            hit.get("path"): hit.get("score")
            for hit in input_knowledge_hits
            if isinstance(hit, dict)
        }
        for kref in record_dict.get("knowledge_refs", []):
            if not isinstance(kref, dict):
                continue
            path_value = kref.get("path")
            if path_value not in scores:
                continue  # da bao o luat 3
            if kref.get("score") != scores[path_value]:
                errors.append(
                    f"knowledge_ref '{path_value}' co score {kref.get('score')} "
                    f"khong khop score that {scores[path_value]}"
                )

    return len(errors) == 0, errors
