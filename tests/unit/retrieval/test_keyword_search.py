from pathlib import Path
from project_sentinel.retrieval.keyword_search import (
    KnowledgeDoc,
    expand_query_tokens,
    score_doc,
    search,
    snippet_for,
    tokenize,
)
from project_sentinel.retrieval.knowledge_retriever import retrieve_knowledge


def test_retrieve_knowledge_sqli(knowledge_dir):
    hits = retrieve_knowledge(
        title="Potential SQL injection",
        rule_id="java-sql-statement-execution",
        cwe=["CWE-89"],
        owasp=["A03:2021-Injection"],
        knowledge_dir=knowledge_dir,
        top_k=3,
    )

    assert len(hits) > 0
    paths = [h.path for h in hits]
    assert any("sql-injection" in p or "owasp-top10" in p for p in paths)
    assert hits[0].score > 0.0
    assert hits[0].snippet != ""


def test_retrieve_knowledge_deserialization(knowledge_dir):
    hits = retrieve_knowledge(
        title="Insecure Deserialization",
        rule_id="java-unsafe-deserialization",
        cwe=["CWE-502"],
        owasp=["A08:2021-Software and Data Integrity Failures"],
        knowledge_dir=knowledge_dir,
        top_k=3,
    )

    assert len(hits) > 0
    paths = [h.path for h in hits]
    assert any("deserialization" in p or "cwe-502" in p or "owasp" in p for p in paths)


def test_retrieve_knowledge_empty_query(knowledge_dir):
    hits = retrieve_knowledge(
        title="",
        rule_id="",
        cwe=[],
        owasp=[],
        knowledge_dir=knowledge_dir,
    )
    assert hits == []


def test_retrieve_knowledge_missing_dir(tmp_path):
    missing_dir = tmp_path / "non_existent_kb"
    hits = retrieve_knowledge(
        title="SQL Injection",
        knowledge_dir=missing_dir,
    )
    assert hits == []


def test_tokenize_handles_technical_identifiers():
    tokens = tokenize("findAccountById CWE-89 java.lang.Runtime.exec owasp-a03")
    assert "cwe-89" in tokens
    assert "cwe89" in tokens
    assert "find" in tokens
    assert "account" in tokens
    assert "runtime" in tokens
    assert "exec" in tokens


def test_expand_query_tokens_security_taxonomy():
    expanded = expand_query_tokens(["ssrf", "rce", "jwt"])
    assert "cwe-918" in expanded or "server-side" in expanded
    assert "cwe-78" in expanded or "command" in expanded
    assert "cwe-347" in expanded or "token" in expanded


def test_snippet_extraction_centers_around_query_term():
    body = "Intro text here. " + "word " * 30 + "Dangerous SQL Injection vulnerability occurs here. " + "tail " * 30
    snippet = snippet_for(["sql", "injection"], body, width=120)
    assert "SQL Injection" in snippet or "injection" in snippet.lower()
    assert len(snippet) <= 130


def test_search_with_category_filter(knowledge_dir):
    vuln_hits = search("vulnerability", knowledge_dir=knowledge_dir, category="vulnerabilities", limit=10)
    for _, doc, _ in vuln_hits:
        assert "vulnerabilities" in doc.path.as_posix()

    tool_hits = search("scanner", knowledge_dir=knowledge_dir, category="tools", limit=10)
    for _, doc, _ in tool_hits:
        assert "tools" in doc.path.as_posix()


def test_score_doc_no_path_substring_false_positive():
    """Ensure substring matches like 'cat' inside 'concat.md' do not match path tokens."""
    doc = KnowledgeDoc(
        path=Path("vulnerabilities/sql-injection-concat.md"),
        title="Unrelated Topic",
        tags=["security", "database"],
        headings=["Introduction"],
        body="This document discusses database security concepts.",
    )
    # 'cat' is a substring of 'concat', but 'cat' is not a distinct token in the path
    score = score_doc(query_tokens=["cat"], original_tokens=["cat"], doc=doc)
    assert score == 0.0


def test_score_doc_term_frequency_boost():
    """A document with repeated matching terms in body should rank higher due to TF."""
    doc_low_tf = KnowledgeDoc(
        path=Path("docs/doc_a.md"),
        title="Document Alpha",
        tags=[],
        headings=[],
        body="This mentions deserialization once in the text.",
    )
    doc_high_tf = KnowledgeDoc(
        path=Path("docs/doc_b.md"),
        title="Document Beta",
        tags=[],
        headings=[],
        body=" ".join(["deserialization vulnerability flaw"] * 10),
    )

    score_low = score_doc(query_tokens=["deserialization"], original_tokens=["deserialization"], doc=doc_low_tf)
    score_high = score_doc(query_tokens=["deserialization"], original_tokens=["deserialization"], doc=doc_high_tf)

    assert score_high > score_low


def test_score_doc_phrase_boost():
    """A document with the exact two-word phrase should receive a phrase boost over scattered words."""
    doc_exact_phrase = KnowledgeDoc(
        path=Path("docs/doc_exact.md"),
        title="Command Execution Guide",
        tags=[],
        headings=[],
        body="This guide details command injection prevention mechanisms.",
    )
    doc_scattered_words = KnowledgeDoc(
        path=Path("docs/doc_scattered.md"),
        title="General Guide",
        tags=[],
        headings=[],
        body="Execute the command on terminal to check if the injection of dependencies succeeded.",
    )

    query = "command injection"
    q_tokens = ["command", "injection"]
    score_phrase = score_doc(q_tokens, q_tokens, doc_exact_phrase, raw_query=query)
    score_scattered = score_doc(q_tokens, q_tokens, doc_scattered_words, raw_query=query)

    # Exact phrase matches in body should yield higher score due to +8.0 phrase boost
    assert score_phrase > score_scattered



