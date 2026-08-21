"""Provenance phải khớp CHÍNH XÁC, không chỉ khớp đường dẫn.

Validator cũ kiểm rằng ID, vị trí, CWE và *đường dẫn* bằng chứng đều có trong input.
Nhưng nó không kiểm **nội dung**. Một record có thể dùng đường dẫn thật, dòng thật,
rồi bịa ra đoạn mã tại vị trí đó — và vẫn qua được toàn bộ ba lớp.

Đó là kẽ hở nguy hiểm nhất còn lại: mọi thứ *trông* có nguồn gốc, nên người đọc tin
đoạn mã được trích là thật.
"""

import pytest

from project_sentinel.analysis.validators import validate_provenance

INPUT_LOCATIONS = [{"file": "Lesson.java", "line": 47}]
INPUT_SOURCE_EVIDENCE = [
    {
        "type": "source",
        "path": "Lesson.java",
        "start_line": 40,
        "end_line": 54,
        "content": "statement.executeUpdate(query);",
    }
]
INPUT_KNOWLEDGE = [{"path": "knowledge/cwe-89.md", "score": 0.95}]


def _record(**overrides):
    base = {
        "group_key": "grp-that",
        "source_finding_ids": ["f-01"],
        "locations": list(INPUT_LOCATIONS),
        "cwe": ["CWE-89"],
        "owasp": ["A03:2021-Injection"],
        "knowledge_refs": [dict(INPUT_KNOWLEDGE[0])],
        "evidence": [
            {
                "type": "source",
                "path": "Lesson.java",
                "start_line": 40,
                "end_line": 54,
                "content": "statement.executeUpdate(query);",
            }
        ],
    }
    base.update(overrides)
    return base


def _check(record):
    return validate_provenance(
        record_dict=record,
        input_group_finding_ids=["f-01"],
        input_locations=INPUT_LOCATIONS,
        input_knowledge_paths=[hit["path"] for hit in INPUT_KNOWLEDGE],
        input_cwes=["CWE-89"],
        input_owasps=["A03:2021-Injection"],
        input_source_evidence=INPUT_SOURCE_EVIDENCE,
        input_group_key="grp-that",
        input_knowledge_hits=INPUT_KNOWLEDGE,
    )


def test_a_faithful_record_passes():
    valid, errors = _check(_record())
    assert valid, errors


# --- nội dung bằng chứng ----------------------------------------------------


def test_invented_source_content_at_a_real_path_is_rejected():
    """Đường dẫn thật, dòng thật, nhưng đoạn mã bịa ra."""
    record = _record(
        evidence=[
            {
                "type": "source",
                "path": "Lesson.java",
                "start_line": 40,
                "end_line": 54,
                "content": "String q = \"SELECT * FROM secret\"; // dong nay khong ton tai",
            }
        ]
    )
    valid, errors = _check(record)
    assert not valid
    assert any("content" in e for e in errors)


@pytest.mark.parametrize(
    "field,value", [("start_line", 1), ("end_line", 999)]
)
def test_a_shifted_line_range_is_rejected(field, value):
    evidence = dict(INPUT_SOURCE_EVIDENCE[0])
    evidence[field] = value
    valid, errors = _check(_record(evidence=[evidence]))
    assert not valid


# --- group key --------------------------------------------------------------


def test_a_wrong_group_key_is_rejected():
    valid, errors = _check(_record(group_key="grp-bia-dat"))
    assert not valid
    assert any("group_key" in e for e in errors)


# --- knowledge --------------------------------------------------------------


def test_an_invented_knowledge_score_is_rejected():
    """Điểm liên quan là số do hệ thống tính, không phải thứ Agent được đặt."""
    valid, errors = _check(
        _record(knowledge_refs=[{"path": "knowledge/cwe-89.md", "score": 0.99}])
    )
    assert not valid
    assert any("score" in e for e in errors)


# --- các luật cũ vẫn phải còn ------------------------------------------------


def test_an_invented_finding_id_is_still_rejected():
    valid, _ = _check(_record(source_finding_ids=["f-01", "f-khong-co"]))
    assert not valid


def test_an_invented_location_is_still_rejected():
    valid, _ = _check(_record(locations=[{"file": "Khac.java", "line": 1}]))
    assert not valid


def test_an_invented_cwe_is_still_rejected():
    valid, _ = _check(_record(cwe=["CWE-89", "CWE-79"]))
    assert not valid


# --- tương thích ngược -------------------------------------------------------


def test_the_new_checks_are_skipped_when_the_input_is_not_supplied():
    """Caller cũ không truyền input mới thì không được tự nhiên fail."""
    valid, errors = validate_provenance(
        record_dict=_record(group_key="bat-ky"),
        input_group_finding_ids=["f-01"],
        input_locations=INPUT_LOCATIONS,
        input_knowledge_paths=["knowledge/cwe-89.md"],
        input_cwes=["CWE-89"],
        input_owasps=["A03:2021-Injection"],
        input_source_evidence=INPUT_SOURCE_EVIDENCE,
    )
    assert valid, errors
