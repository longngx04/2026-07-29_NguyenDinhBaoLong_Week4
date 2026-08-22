"""
Source evidence extraction for the Security Analysis Agent.
Safely extracts code windows around scanner finding locations with path traversal protections.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from project_sentinel.models import EvidenceItem
from project_sentinel.pathutil import canonicalize_source_path

MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB limit
MAX_LINE_COUNT = 50000


@dataclass
class SourceEvidence:
    """Extracted source evidence snippet around a finding location."""
    path: str
    start_line: int
    end_line: int
    content: str
    error: Optional[str] = None

    def to_evidence_item(self) -> Optional[EvidenceItem]:
        """Convert to standard EvidenceItem data model if valid, or None if error."""
        if self.error or not self.content or self.start_line < 0:
            return None
        return EvidenceItem(

            type="source",
            path=self.path,
            start_line=self.start_line,
            end_line=self.end_line,
            content=self.content
        )


def extract_source_window(
    project_root: Path,
    target_root: Path,
    relative_path: str,
    line: int,
    radius: int = 4
) -> SourceEvidence:
    """Extract code window around (relative_path, line) under project_root and target_root.
    
    Security & Boundary guarantees:
    - Path must resolve strictly inside both project_root and target_root.
    - Path traversal (..) and symlink escapes are rejected.
    - Max file size and line count limits are enforced.
    - Missing files return a typed SourceEvidence with error note without crashing.
    """
    if not relative_path or not str(relative_path).strip():
        return SourceEvidence(
            path="",
            start_line=0,
            end_line=0,
            content="",
            error="Empty relative path provided"
        )

    clean_rel_path = canonicalize_source_path(relative_path)
    if not clean_rel_path:
        return SourceEvidence(
            path="",
            start_line=0,
            end_line=0,
            content="",
            error="Empty relative path provided"
        )

    root_resolved = project_root.resolve()
    target_root_resolved = target_root.resolve()
    target_path = (project_root / clean_rel_path).resolve()

    # Project root boundary check
    try:
        target_path.relative_to(root_resolved)
    except ValueError:
        return SourceEvidence(
            path=clean_rel_path,
            start_line=0,
            end_line=0,
            content="",
            error=f"Security violation: path '{clean_rel_path}' escapes project root"
        )

    # Target root boundary check
    try:
        target_path.relative_to(target_root_resolved)
    except ValueError:
        return SourceEvidence(
            path=clean_rel_path,
            start_line=0,
            end_line=0,
            content="",
            error=f"Security violation: path '{clean_rel_path}' is outside target_root boundary"
        )

    if not target_path.exists() or not target_path.is_file():
        return SourceEvidence(
            path=clean_rel_path,
            start_line=0,
            end_line=0,
            content="",
            error=f"Source file not found: {clean_rel_path}"
        )

    # File size limit check
    try:
        stat = target_path.stat()
        if stat.st_size > MAX_FILE_SIZE_BYTES:
            return SourceEvidence(
                path=clean_rel_path,
                start_line=0,
                end_line=0,
                content="",
                error=f"Source file exceeds max size limit ({stat.st_size} bytes)"
            )
    except Exception as e:
        return SourceEvidence(
            path=clean_rel_path,
            start_line=0,
            end_line=0,
            content="",
            error=f"Failed to stat file: {e}"
        )

    # Read lines safely
    try:
        lines = target_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception as e:
        return SourceEvidence(
            path=clean_rel_path,
            start_line=0,
            end_line=0,
            content="",
            error=f"Failed to read file content: {e}"
        )

    total_lines = len(lines)
    if total_lines == 0:
        return SourceEvidence(
            path=clean_rel_path,
            start_line=0,
            end_line=0,
            content="",
            error="Source file is empty"
        )

    if total_lines > MAX_LINE_COUNT:
        return SourceEvidence(
            path=clean_rel_path,
            start_line=0,
            end_line=0,
            content="",
            error=f"Source file exceeds max line count limit ({total_lines} > {MAX_LINE_COUNT})"
        )

    if line <= 0:
        line = 1

    start_line = max(1, line - radius)
    end_line = min(total_lines, line + radius)

    snippet_lines = lines[start_line - 1 : end_line]
    content = "\n".join(snippet_lines)

    return SourceEvidence(
        path=clean_rel_path,
        start_line=start_line,
        end_line=end_line,
        content=content
    )


def _dast_evidence(finding: dict) -> SourceEvidence:
    """Bang chung cua mot finding dong la chinh alert do ZAP quan sat."""
    instances = finding.get("instances") or []
    if not instances:
        return SourceEvidence(
            path=str(finding.get("file_or_url") or ""),
            start_line=0,
            end_line=0,
            content="",
            error="Finding DAST khong co instance nao de lam bang chung",
        )

    total = finding.get("instances_total", len(instances))
    lines = [
        f"Alert: {finding.get('title') or finding.get('rule_id')}",
        f"So vi tri bi anh huong: {total}",
    ]
    for instance in instances:
        line = f"- {instance.get('method', 'GET')} {instance.get('url', '')}"
        if instance.get("param"):
            line += f" [param={instance['param']}]"
        lines.append(line)

    return SourceEvidence(
        path=str(instances[0].get("url") or finding.get("file_or_url") or ""),
        start_line=0,
        end_line=0,
        content="\n".join(lines),
    )


def evidence_for_finding(
    finding: dict, *, project_root: Path, target_root: Path, radius: int = 4
) -> SourceEvidence:
    """Chon duong trich bang chung theo hinh dang cua finding.

    Finding co file+line di dung duong cu, khong doi mot byte hanh vi
    (AGENTS.md §2.1). zap_normalizer dat `line: 0` chu khong phai None, nen
    dieu phoi bang `line > 0`.
    """
    location = finding.get("file_or_url")
    line = finding.get("line")
    if isinstance(line, int) and line > 0 and location and "://" not in str(location):
        return extract_source_window(
            project_root, target_root, str(location), line, radius
        )
    if str(finding.get("tool")) == "zap":
        return _dast_evidence(finding)
    return extract_source_window(
        project_root, target_root, str(location or ""), line or 0, radius
    )

