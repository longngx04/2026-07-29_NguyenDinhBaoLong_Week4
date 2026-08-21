from project_sentinel.analysis.evidence import extract_source_window


def test_extract_source_window_valid(tmp_path):
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    sample_file = src_dir / "Vulnerable.java"
    content_lines = [f"// line {i}" for i in range(1, 21)]
    sample_file.write_text("\n".join(content_lines), encoding="utf-8")

    evidence = extract_source_window(
        project_root=tmp_path,
        target_root=src_dir,
        relative_path="src/Vulnerable.java",
        line=10,
        radius=3
    )

    assert evidence.error is None
    assert evidence.path == "src/Vulnerable.java"
    assert evidence.start_line == 7
    assert evidence.end_line == 13
    assert "// line 10" in evidence.content
    assert "// line 7" in evidence.content
    assert "// line 13" in evidence.content
    assert "// line 6" not in evidence.content
    item = evidence.to_evidence_item()
    assert item is not None
    assert item.type == "source"


def test_extract_source_window_missing_file(tmp_path):
    evidence = extract_source_window(
        project_root=tmp_path,
        target_root=tmp_path,
        relative_path="non_existent.py",
        line=5
    )
    assert evidence.error is not None
    assert "not found" in evidence.error
    assert evidence.start_line == 0
    assert evidence.end_line == 0
    assert evidence.to_evidence_item() is None


def test_extract_source_window_path_traversal(tmp_path):
    sub_root = tmp_path / "sub"
    sub_root.mkdir()
    secret = tmp_path / "secret.txt"
    secret.write_text("SECRET DATA", encoding="utf-8")

    evidence = extract_source_window(
        project_root=sub_root,
        target_root=sub_root,
        relative_path="../secret.txt",
        line=1
    )
    assert evidence.error is not None
    assert "escapes project root" in evidence.error
    assert "SECRET DATA" not in evidence.content


def test_extract_rejects_outside_target_root(tmp_path):
    target = tmp_path / "benchmarks/targets/webgoat"
    target.mkdir(parents=True)
    (tmp_path / "src/project_sentinel").mkdir(parents=True)
    (tmp_path / "src/project_sentinel/config.py").write_text("secret", encoding="utf-8")

    ev = extract_source_window(
        project_root=tmp_path,
        target_root=target,
        relative_path="src/project_sentinel/config.py",
        line=1
    )
    assert ev.error is not None
    assert "target" in ev.error.lower() or "boundary" in ev.error.lower()


def test_canonicalize_legacy_webgoat_path(tmp_path):
    target = tmp_path / "benchmarks/targets/webgoat/src"
    target.mkdir(parents=True)
    src = target / "App.java"
    src.write_text("\n".join(f"// line {i}" for i in range(1, 6)), encoding="utf-8")

    ev = extract_source_window(
        project_root=tmp_path,
        target_root=tmp_path / "benchmarks/targets/webgoat",
        relative_path="targets/webgoat/src/App.java",
        line=3,
        radius=1,
    )
    assert ev.error is None
    assert ev.path == "benchmarks/targets/webgoat/src/App.java"
    assert "// line 3" in ev.content


def test_extract_source_window_max_line_count(tmp_path, monkeypatch):
    monkeypatch.setattr("project_sentinel.analysis.evidence.MAX_LINE_COUNT", 5)
    f = tmp_path / "long.txt"
    f.write_text("\n".join([f"line {i}" for i in range(10)]), encoding="utf-8")

    ev = extract_source_window(
        project_root=tmp_path,
        target_root=tmp_path,
        relative_path="long.txt",
        line=1
    )
    assert ev.error is not None
    assert "max line count limit" in ev.error
