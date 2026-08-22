import json

import pytest

from project_sentinel.ingestion.merge_findings import merge_files


def _write(path, source, finding_id):
    path.write_text(
        json.dumps(
            {
                "source": source,
                "count": 1,
                "findings": [{"id": finding_id, "rule_id": "rule"}],
            }
        ),
        encoding="utf-8",
    )


def test_sast_and_dast_findings_can_be_merged(tmp_path):
    sast = tmp_path / "sast.json"
    dast = tmp_path / "dast.json"
    output = tmp_path / "all.json"
    _write(sast, "opengrep", "opengrep-001")
    _write(dast, "zap", "zap-10021-abc")
    merged = merge_files([sast, dast], output)
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert [item["id"] for item in merged] == ["opengrep-001", "zap-10021-abc"]
    assert payload["source"] == "opengrep+zap"
    assert payload["count"] == 2


def test_duplicate_ids_fail_instead_of_overwriting_provenance(tmp_path):
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    _write(first, "one", "same-id")
    _write(second, "two", "same-id")
    with pytest.raises(ValueError, match="Duplicate finding id"):
        merge_files([first, second], tmp_path / "out.json")
