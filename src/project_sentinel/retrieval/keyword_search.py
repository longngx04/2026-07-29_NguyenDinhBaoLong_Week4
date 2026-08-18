"""Keyword search over the local Markdown knowledge base."""

from __future__ import annotations

import argparse
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path

DEFAULT_KNOWLEDGE = Path("data/knowledge-base")

# Enhanced tokenizer for technical security terms: identifiers, hyphens, colons, dots
WORD_RE = re.compile(r"[a-z0-9]+(?:[-_:.][a-z0-9]+)*", re.IGNORECASE)
CAMEL_CASE_RE = re.compile(r"([a-z])([A-Z])")

# Comprehensive Security Taxonomy covering all classes in data/knowledge-base/
SYNONYMS: dict[str, set[str]] = {
    # SQL Injection
    "sql": {"sqli", "injection", "cwe-89", "cwe89", "a03", "preparedstatement", "concat"},
    "sqli": {"sql", "injection", "cwe-89", "cwe89", "a03"},
    "injection": {"sql", "sqli", "command", "cmdi", "code", "a03"},
    # Cross-Site Scripting (XSS)
    "xss": {"cross-site", "scripting", "cwe-79", "cwe79", "a03", "a07", "stored", "reflected", "dom"},
    "cross-site": {"xss", "scripting", "csrf"},
    "scripting": {"xss", "cross-site"},
    # Command Injection / RCE
    "command": {"cmdi", "rce", "exec", "runtime", "processbuilder", "cwe-78", "cwe78", "a03"},
    "cmdi": {"command", "injection", "exec", "rce", "cwe-78", "cwe78"},
    "rce": {"command", "execution", "remote", "code", "cwe-78", "cwe-502"},
    "exec": {"command", "runtime", "processbuilder", "cwe-78"},
    # Insecure Deserialization
    "deserialization": {"deserializing", "deserialize", "serialize", "cwe-502", "cwe502", "a08", "objectinputstream", "jackson", "ysoserial"},
    "deserialize": {"deserialization", "cwe-502", "cwe502", "a08"},
    "serialize": {"deserialization", "cwe-502", "cwe502"},
    # Path Traversal / Directory Traversal
    "traversal": {"path", "directory", "lfi", "cwe-22", "cwe22", "a01", "file"},
    "path": {"traversal", "directory", "cwe-22", "cwe22"},
    "directory": {"traversal", "path", "cwe-22", "cwe22"},
    "lfi": {"traversal", "path", "file", "cwe-22"},
    # SSRF (Server-Side Request Forgery)
    "ssrf": {"server-side", "request", "forgery", "cwe-918", "cwe918", "a10", "httpclient", "urlconnection"},
    # XXE (XML External Entity)
    "xxe": {"xml", "external", "entity", "cwe-611", "cwe611", "a05", "documentbuilder", "saxparser"},
    "xml": {"xxe", "entity", "cwe-611", "cwe611"},
    # CSRF (Cross-Site Request Forgery)
    "csrf": {"cross-site", "request", "forgery", "xsrf", "cwe-352", "cwe352", "a01", "samesite"},
    "xsrf": {"csrf", "cross-site", "request", "forgery", "cwe-352", "cwe352"},
    # IDOR / Broken Access Control
    "idor": {"insecure", "direct", "object", "reference", "authorization", "cwe-639", "cwe639", "cwe-284", "cwe-862", "a01"},
    "authorization": {"auth", "idor", "access", "control", "cwe-862", "cwe-284", "a01"},
    # Broken Authentication
    "auth": {"authentication", "authorization", "password", "credential", "session", "cwe-287", "cwe287", "cwe-384", "a07"},
    "authentication": {"auth", "password", "credential", "session", "cwe-287", "cwe287", "a07"},
    # JWT Weak Verification
    "jwt": {"token", "json", "web", "signature", "algorithm", "none", "cwe-347", "cwe347", "cwe-1295", "a02", "hs256", "rs256"},
    # Security Misconfiguration
    "misconfiguration": {"config", "debug", "default", "cors", "cwe-16", "cwe16", "cwe-1004", "a05"},
    # Vulnerable Components / Dependencies
    "components": {"vulnerable", "dependency", "dependencies", "outdated", "cve", "cwe-1104", "cwe1104", "a06"},
    "dependencies": {"components", "vulnerable", "outdated", "cve", "cwe-1104", "a06"},
    # HTML / Parameter Tampering
    "tampering": {"html", "parameter", "price", "hidden", "cwe-472", "cwe472"},
    # Direct CWE mappings (bidirectional)
    "cwe-89": {"sql", "sqli", "injection"},
    "cwe89": {"sql", "sqli", "injection"},
    "cwe-79": {"xss", "cross-site", "scripting"},
    "cwe79": {"xss", "cross-site", "scripting"},
    "cwe-78": {"command", "cmdi", "exec", "rce", "runtime"},
    "cwe78": {"command", "cmdi", "exec", "rce"},
    "cwe-502": {"deserialization", "deserialize", "serialize"},
    "cwe502": {"deserialization", "deserialize", "serialize"},
    "cwe-22": {"traversal", "path", "directory", "lfi"},
    "cwe22": {"traversal", "path", "directory", "lfi"},
    "cwe-918": {"ssrf", "server-side", "request", "forgery"},
    "cwe918": {"ssrf", "server-side", "request", "forgery"},
    "cwe-611": {"xxe", "xml", "external", "entity"},
    "cwe611": {"xxe", "xml", "external", "entity"},
    "cwe-352": {"csrf", "cross-site", "request", "forgery"},
    "cwe352": {"csrf", "cross-site", "request", "forgery"},
    "cwe-639": {"idor", "authorization", "access", "control"},
    "cwe639": {"idor", "authorization", "access", "control"},
    "cwe-284": {"idor", "authorization", "access", "control"},
    "cwe-862": {"idor", "authorization", "access", "control"},
    "cwe-287": {"auth", "authentication", "session", "password"},
    "cwe287": {"auth", "authentication", "session", "password"},
    "cwe-384": {"auth", "authentication", "session"},
    "cwe-347": {"jwt", "token", "signature"},
    "cwe347": {"jwt", "token", "signature"},
    "cwe-1295": {"jwt", "token", "algorithm"},
    "cwe-16": {"misconfiguration", "config", "debug"},
    "cwe16": {"misconfiguration", "config", "debug"},
    "cwe-1004": {"misconfiguration", "cookie", "httponly"},
    "cwe-1104": {"components", "vulnerable", "dependency", "dependencies"},
    "cwe1104": {"components", "vulnerable", "dependency", "dependencies"},
    "cwe-472": {"tampering", "html", "parameter"},
    "cwe472": {"tampering", "html", "parameter"},
    # OWASP Top 10 mappings
    "a01": {"access", "control", "idor", "csrf", "path", "traversal"},
    "a02": {"cryptographic", "jwt", "crypto", "token"},
    "a03": {"injection", "sql", "sqli", "xss", "command", "rce"},
    "a04": {"insecure", "design"},
    "a05": {"misconfiguration", "xxe", "security"},
    "a06": {"vulnerable", "components", "outdated"},
    "a07": {"identification", "authentication", "auth", "xss"},
    "a08": {"integrity", "deserialization", "software"},
    "a09": {"logging", "monitoring"},
    "a10": {"ssrf", "server-side", "request", "forgery"},
    # Tool and Format keywords
    "opengrep": {"sast", "scanner", "rules", "check_id"},
    "sast": {"opengrep", "scanner", "static", "analysis"},
    "normalized": {"findings", "schema", "sarif"},
}


@dataclass
class KnowledgeDoc:
    path: Path
    title: str
    tags: list[str]
    headings: list[str]
    body: str


def tokenize(text: str) -> list[str]:
    """Tokenize technical security text into a full (non-deduplicated) stream of normalized terms."""
    if not text:
        return []
    # Expand camelCase into separate words (e.g. 'findAccountById' -> 'find Account By Id')
    expanded_text = CAMEL_CASE_RE.sub(r"\1 \2", text)
    tokens: list[str] = []

    for match in WORD_RE.finditer(expanded_text):
        raw_tok = match.group(0).lower().strip(".:;,")
        if not raw_tok or len(raw_tok) < 2:
            continue
        tokens.append(raw_tok)

        # Standardize CWE hyphen / no-hyphen: 'cwe-89' -> also add 'cwe89'
        if raw_tok.startswith("cwe-") and raw_tok[4:].isalnum():
            tokens.append("cwe" + raw_tok[4:])
        elif raw_tok.startswith("cwe") and raw_tok[3:].isdigit():
            tokens.append("cwe-" + raw_tok[3:])

        # Split sub-tokens if term contains hyphen or dot (e.g., 'java.lang.Runtime' -> 'java', 'lang', 'runtime')
        if any(sep in raw_tok for sep in ("-", ".", "_")):
            sub_parts = re.split(r"[-._]+", raw_tok)
            for sub in sub_parts:
                sub = sub.strip()
                if len(sub) >= 2:
                    tokens.append(sub)

    return tokens


def expand_query_tokens(tokens: list[str]) -> list[str]:
    """Expand query terms with domain-specific security synonyms, preserving uniqueness."""
    expanded: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        if token not in seen:
            expanded.append(token)
            seen.add(token)
        for alias in SYNONYMS.get(token, ()):
            if alias not in seen:
                expanded.append(alias)
                seen.add(alias)
    return expanded


def parse_markdown(path: Path) -> KnowledgeDoc:
    """Parse markdown document extract metadata, headings, tags, and body."""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    title = path.stem.replace("-", " ").title()
    tags: list[str] = []
    headings: list[str] = []
    body_start = 0

    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                body_start = i + 1
                break
            line = lines[i].strip()
            if line.lower().startswith("title:"):
                title = line.split(":", 1)[1].strip().strip("\"'")
            elif line.lower().startswith("tags:"):
                raw = line.split(":", 1)[1].strip()
                if raw.startswith("[") and raw.endswith("]"):
                    raw = raw[1:-1]
                tags = [t.strip().strip("\"'") for t in raw.split(",") if t.strip()]

    body_lines = lines[body_start:]
    for line in body_lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            heading_text = stripped.lstrip("#").strip()
            headings.append(heading_text)
            if stripped.startswith("# ") and title == path.stem.replace("-", " ").title():
                title = heading_text

    body = "\n".join(body_lines).strip()
    return KnowledgeDoc(path=path, title=title, tags=tags, headings=headings, body=body)


def load_docs(knowledge_dir: Path = DEFAULT_KNOWLEDGE) -> list[KnowledgeDoc]:
    """Load all markdown documentation files from knowledge directory."""
    if not knowledge_dir.is_dir():
        raise FileNotFoundError(f"Knowledge directory not found: {knowledge_dir}")
    return [parse_markdown(path) for path in sorted(knowledge_dir.rglob("*.md"))]


def score_doc(
    query_tokens: list[str],
    original_tokens: list[str],
    doc: KnowledgeDoc,
    raw_query: str = "",
) -> float:
    """Multi-field BM25/TF-IDF inspired relevance scoring."""
    if not query_tokens:
        return 0.0

    title_tokens = set(tokenize(doc.title))
    tag_tokens = set(tokenize(" ".join(doc.tags)))
    heading_tokens = set(tokenize(" ".join(doc.headings)))
    path_tokens = set(tokenize(doc.path.as_posix()))
    body_token_list = tokenize(doc.body)
    body_tokens = set(body_token_list)

    searchable_text = f"{doc.title} {' '.join(doc.tags)} {' '.join(doc.headings)} {doc.body}".lower()

    score = 0.0
    original_set = set(original_tokens)

    for token in query_tokens:
        is_original = token in original_set
        weight = 1.0 if is_original else 0.4

        # Title match (high priority)
        if token in title_tokens:
            score += 6.0 * weight

        # Tags match (structured metadata)
        if token in tag_tokens:
            score += 5.0 * weight

        # Headings match
        if token in heading_tokens:
            score += 3.0 * weight

        # Path token-level match (no substring false positives)
        if token in path_tokens:
            score += 4.0 * weight

        # Body match with term frequency damping
        if token in body_tokens:
            tf = body_token_list.count(token)
            tf_score = 1.0 + math.log1p(min(tf, 20))
            score += tf_score * weight

    # Normalized raw query phrase boost
    phrase = " ".join((raw_query or " ".join(original_tokens)).lower().split())
    if len(phrase.split()) >= 2:
        if phrase in searchable_text:
            score += 8.0
        # Check title exact phrase match
        if phrase in doc.title.lower():
            score += 10.0
        # Exact token sequence in tags
        if any(phrase in tag.lower() for tag in doc.tags):
            score += 6.0

    return score


def snippet_for(query_tokens: list[str], body: str, width: int = 240) -> str:
    """Extract contextual snippet containing the most relevant query terms."""
    if not body:
        return ""

    paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
    if not paragraphs:
        paragraphs = [line.strip() for line in body.splitlines() if line.strip()]

    target_tokens = [t for t in query_tokens if len(t) >= 3] or query_tokens
    best_para = ""
    max_matches = -1

    for para in paragraphs:
        if para.startswith("#"):
            continue
        para_lower = para.lower()
        matches = sum(1 for tok in target_tokens if tok in para_lower)
        if matches > max_matches:
            max_matches = matches
            best_para = para

    selected = best_para or (paragraphs[0] if paragraphs else body)
    clean = " ".join(selected.replace("`", "").replace("*", "").split())

    if len(clean) <= width:
        return clean

    # Center snippet around first primary match
    lower_clean = clean.lower()
    first_idx = -1
    for tok in target_tokens:
        idx = lower_clean.find(tok)
        if idx != -1:
            first_idx = idx
            break

    if first_idx != -1:
        start = max(0, first_idx - 50)
        end = min(len(clean), start + width)
        snippet = clean[start:end].strip()
        if start > 0:
            snippet = "…" + snippet
        if end < len(clean):
            snippet = snippet + "…"
        return snippet

    return clean[:width].strip() + "…"


def search(
    query: str,
    knowledge_dir: Path = DEFAULT_KNOWLEDGE,
    limit: int = 5,
    category: str | None = None,
) -> list[tuple[float, KnowledgeDoc, str]]:
    """Search knowledge base with ranking and snippet generation."""
    raw_query = query.strip()
    if not raw_query:
        return []

    # Get deduplicated original tokens for query expansion while preserving order
    all_query_tokens = tokenize(raw_query)
    original_tokens: list[str] = []
    seen: set[str] = set()
    for tok in all_query_tokens:
        if tok not in seen:
            original_tokens.append(tok)
            seen.add(tok)

    if not original_tokens:
        return []

    query_tokens = expand_query_tokens(original_tokens)
    docs = load_docs(knowledge_dir)

    if category:
        docs = [d for d in docs if category.lower() in d.path.as_posix().lower()]

    ranked: list[tuple[float, KnowledgeDoc, str]] = []
    for doc in docs:
        score = score_doc(query_tokens, original_tokens, doc, raw_query=raw_query)
        if score <= 0.0:
            continue
        snippet = snippet_for(original_tokens or query_tokens, doc.body)
        ranked.append((score, doc, snippet))

    # Sort descending by score, tie-break by path
    ranked.sort(key=lambda row: (-row[0], row[1].path.as_posix()))
    return ranked[:limit]


def run_search(
    query: str,
    knowledge_dir: Path = DEFAULT_KNOWLEDGE,
    limit: int = 5,
    category: str | None = None,
) -> int:
    """Run search from CLI and format results to stdout."""
    hits = search(query, knowledge_dir=knowledge_dir, limit=limit, category=category)
    if not hits:
        print(f"No knowledge matches for: {query!r}")
        return 1

    print(f"Query: {query!r} — {len(hits)} hit(s)\n")
    for i, (score, doc, snippet) in enumerate(hits, start=1):
        print(f"{i}. [{score:.1f}] {doc.title}")
        print(f"   path: {doc.path.as_posix()}")
        if doc.tags:
            print(f"   tags: {', '.join(doc.tags)}")
        print(f"   snippet: {snippet}")
        print()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Comprehensive keyword search over data/knowledge-base/.")
    parser.add_argument("query", nargs="+", help='Search query, e.g. "SQL Injection", "Path Traversal", "CWE-502"')
    parser.add_argument("--knowledge", type=Path, default=DEFAULT_KNOWLEDGE, help="Path to knowledge base directory")
    parser.add_argument("--limit", type=int, default=5, help="Maximum number of hits to return")
    parser.add_argument("--category", type=str, default=None, help="Filter by category substring (vulnerabilities, owasp, tools)")
    args = parser.parse_args(argv)
    try:
        return run_search(
            " ".join(args.query),
            knowledge_dir=args.knowledge,
            limit=args.limit,
            category=args.category,
        )
    except (FileNotFoundError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

