from pathlib import Path
from project_sentinel.config import AppConfig
from project_sentinel.analysis.grouping import group_findings
from project_sentinel.models import NormalizedFinding, NormalizedLocation
from project_sentinel.analysis.packet_builder import build_analysis_packet


def test_build_analysis_packet(tmp_path):
    # Setup test file
    target_dir = tmp_path / "benchmarks" / "targets" / "webgoat" / "src"
    target_dir.mkdir(parents=True)
    src_file = target_dir / "Test.java"
    src_file.write_text("package test;\npublic class Test {\n  void run() { execute(); }\n}\n", encoding="utf-8")

    rel_path = "benchmarks/targets/webgoat/src/Test.java"

    f1 = NormalizedFinding(
        id="f1",
        rule_id="java-sql-statement-execution",
        title="Potential SQL injection",
        severity="high",
        confidence="MEDIUM",
        location=NormalizedLocation(file=rel_path, line=3),
        cwe=["CWE-89"],
        owasp=["A03:2021-Injection"]
    )
    f2 = NormalizedFinding(
        id="f2",
        rule_id="java-sql-statement-execution",
        title="Potential SQL injection",
        severity="high",
        confidence="MEDIUM",
        location=NormalizedLocation(file=rel_path, line=3),
        cwe=["CWE-89"],
        owasp=["A03:2021-Injection"]
    )

    groups = group_findings([f1, f2])
    assert len(groups) == 1

    config = AppConfig(
        project_root=tmp_path,
        knowledge_dir=Path(__file__).parent.parent.parent.parent / "data" / "knowledge-base",
        schema_path=Path(__file__).parent.parent.parent.parent / "schemas" / "security-analysis-record.schema.json"
    )

    packet = build_analysis_packet(
        group=groups[0],
        config=config,
        project_root=tmp_path,
        target_root=tmp_path / "benchmarks" / "targets" / "webgoat"
    )

    assert packet.group_key == groups[0].group_key
    assert packet.finding_group["source_finding_ids"] == ["f1", "f2"]
    assert len(packet.source_evidence) == 1
    assert packet.source_evidence[0]["path"] == rel_path
    assert "execute()" in packet.source_evidence[0]["content"]
    assert len(packet.knowledge_hits) > 0
    assert packet.output_schema.get("title") == "SecurityAnalysisRecord"


def test_build_analysis_packet_with_limitations(tmp_path):
    f = NormalizedFinding(
        id="f-missing",
        rule_id="java-sql-injection",
        title="Missing file test",
        severity="medium",
        confidence="LOW",
        location=NormalizedLocation(file="missing.java", line=1)
    )
    groups = group_findings([f])
    config = AppConfig(project_root=tmp_path)
    packet = build_analysis_packet(groups[0], config)

    assert "input_limitations" in packet.finding_group
    assert len(packet.finding_group["input_limitations"]) == 1
    assert "missing.java" in packet.finding_group["input_limitations"][0]


def test_sast_evidence_order_matches_locations_order(tmp_path):
    target_dir = tmp_path / "benchmarks" / "targets" / "webgoat" / "src"
    target_dir.mkdir(parents=True)
    f_a = target_dir / "A.java"
    f_b = target_dir / "B.java"
    f_a.write_text("\n".join(f"// line {i}" for i in range(1, 100)), encoding="utf-8")
    f_b.write_text("\n".join(f"// line {i}" for i in range(1, 100)), encoding="utf-8")

    rel_a = "benchmarks/targets/webgoat/src/A.java"
    rel_b = "benchmarks/targets/webgoat/src/B.java"

    findings = [
        NormalizedFinding(id="f3", rule_id="r1", title="T", severity="high", confidence="high",
                          location=NormalizedLocation(file=rel_b, line=50), tool="opengrep", fingerprint="fp1"),
        NormalizedFinding(id="f1", rule_id="r1", title="T", severity="high", confidence="high",
                          location=NormalizedLocation(file=rel_a, line=10), tool="opengrep", fingerprint="fp1"),
        NormalizedFinding(id="f2", rule_id="r1", title="T", severity="high", confidence="high",
                          location=NormalizedLocation(file=rel_a, line=80), tool="opengrep", fingerprint="fp1"),
    ]


    groups = group_findings(findings)
    assert len(groups) == 1
    group = groups[0]

    config = AppConfig(project_root=tmp_path)
    packet = build_analysis_packet(
        group=group,
        config=config,
        project_root=tmp_path,
        target_root=tmp_path / "benchmarks" / "targets" / "webgoat"
    )

    from project_sentinel.analysis.evidence import extract_source_window
    legacy_evs = []
    seen = set()
    for loc in group.locations:
        sev = extract_source_window(tmp_path, tmp_path / "benchmarks" / "targets" / "webgoat", loc.file, loc.line, radius=config.source_radius)
        item = sev.to_evidence_item()
        if item:
            key = (item.path, item.start_line, item.end_line)
            if key not in seen:
                seen.add(key)
                legacy_evs.append(item.to_dict())

    assert packet.source_evidence == legacy_evs, "Thứ tự source evidence của SAST phải khớp hoàn toàn với group.locations cũ"

