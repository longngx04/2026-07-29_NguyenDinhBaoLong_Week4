"""Tiêu chí hoàn thành tìm kiếm tri thức tuần 2 và bao phủ toàn diện knowledge base."""

from pathlib import Path
import pytest
from project_sentinel.retrieval.knowledge_retriever import retrieve_knowledge
from project_sentinel.retrieval.keyword_search import search


def _paths_for(title: str, knowledge_dir, rule_id: str = "", cwe: list[str] | None = None, owasp: list[str] | None = None) -> list[str]:
    hits = retrieve_knowledge(
        title=title,
        rule_id=rule_id,
        cwe=cwe or [],
        owasp=owasp or [],
        knowledge_dir=knowledge_dir,
        top_k=5,
        max_snippet_chars=800,
    )
    return [hit.to_dict()["path"] for hit in hits]


# 1. Các tiêu chí cốt lõi của đề bài tuần 2
def test_search_sql_injection_returns_sql_injection_knowledge(knowledge_dir):
    paths = _paths_for("SQL Injection", knowledge_dir)
    assert paths, "Tìm 'SQL Injection' không trả về tài liệu nào"
    assert any("sql-injection" in path for path in paths), (
        f"Không có tài liệu SQL Injection nào trong kết quả: {paths}"
    )


def test_search_xss_returns_xss_knowledge(knowledge_dir):
    paths = _paths_for("XSS", knowledge_dir)
    assert paths, "Tìm 'XSS' không trả về tài liệu nào"
    assert any("xss" in path for path in paths), (
        f"Không có tài liệu XSS nào trong kết quả: {paths}"
    )


# 2. Bao phủ toàn diện các lớp lỗ hổng khác trong Knowledge Base
@pytest.mark.parametrize(
    "query,expected_keyword",
    [
        ("Path Traversal", "path-traversal"),
        ("Directory Traversal", "path-traversal"),
        ("Insecure Deserialization", "deserialization"),
        ("Command Injection", "command-injection"),
        ("Remote Code Execution", "command-injection"),
        ("SSRF", "ssrf"),
        ("Server-Side Request Forgery", "ssrf"),
        ("XXE", "xxe"),
        ("XML External Entity", "xxe"),
        ("CSRF", "csrf"),
        ("Cross-Site Request Forgery", "csrf"),
        ("IDOR", "idor"),
        ("Broken Access Control", "idor"),
        ("Broken Authentication", "broken-auth"),
        ("JWT Weak Verification", "jwt"),
        ("Security Misconfiguration", "security-misconfiguration"),
        ("Vulnerable Components", "vulnerable-components"),
        ("HTML Tampering", "html-tampering"),
        ("OWASP Top 10", "owasp-top10"),
        ("OpenGrep SAST", "opengrep"),
    ],
)
def test_search_comprehensive_vulnerability_coverage(query: str, expected_keyword: str, knowledge_dir: Path):
    paths = _paths_for(query, knowledge_dir)
    assert paths, f"Tìm '{query}' không trả về kết quả nào"
    assert any(expected_keyword in path for path in paths), (
        f"Tìm '{query}' không chứa '{expected_keyword}' trong kết quả: {paths}"
    )


# 3. Tìm kiếm theo Identifier kỹ thuật (CWE, OWASP Category, Rule ID)
@pytest.mark.parametrize(
    "cwe_id,expected_doc",
    [
        ("CWE-89", "sql-injection"),
        ("CWE-79", "xss"),
        ("CWE-502", "deserialization"),
        ("CWE-22", "path-traversal"),
        ("CWE-78", "command-injection"),
        ("CWE-918", "ssrf"),
        ("CWE-611", "xxe"),
        ("CWE-352", "csrf"),
        ("CWE-347", "jwt"),
    ],
)
def test_search_by_cwe_identifier(cwe_id: str, expected_doc: str, knowledge_dir: Path):
    paths = _paths_for(title="", rule_id="", cwe=[cwe_id], knowledge_dir=knowledge_dir)
    assert paths, f"Tìm theo {cwe_id} không trả về kết quả nào"
    assert any(expected_doc in path for path in paths), (
        f"Tìm theo {cwe_id} không chứa '{expected_doc}': {paths}"
    )


def test_search_by_rule_id(knowledge_dir: Path):
    paths = _paths_for(title="", rule_id="java-sql-statement-execution", knowledge_dir=knowledge_dir)
    assert any("sql-injection" in path for path in paths)


# 4. Anti-hallucination và kiểm soát biên
def test_search_nonsense_term_does_not_invent_documents(knowledge_dir):
    paths = _paths_for("zzzz khong ton tai qqqq", knowledge_dir)
    for path in paths:
        assert Path(path).exists(), (
            f"Kết quả trỏ tới tài liệu không tồn tại: {path}"
        )


def test_search_direct_cli_search_ranking(knowledge_dir: Path):
    hits = search("SQL Injection concatenation", knowledge_dir=knowledge_dir, limit=3)
    assert len(hits) > 0
    top_score, top_doc, top_snippet = hits[0]
    assert "sql-injection" in top_doc.path.as_posix()
    assert top_score > 0
    assert len(top_snippet) > 0
