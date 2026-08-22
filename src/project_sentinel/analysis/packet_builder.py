"""
Packet builder for Security Analysis Agent.
Constructs deterministic AnalysisPacket objects combining deduplicated finding groups,
source evidence snippets, and knowledge retrieval hits.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from project_sentinel.config import AppConfig
from project_sentinel.analysis.evidence import (
    evidence_for_finding,
    extract_source_window,
)
from project_sentinel.analysis.grouping import FindingGroup
from project_sentinel.gateway.allowlist import Allowlist
from project_sentinel.llm.base import AnalysisPacket
from project_sentinel.probe.payload_kinds import PAYLOAD_KIND_TO_TYPE
from project_sentinel.retrieval.knowledge_retriever import retrieve_knowledge

ALL_PAYLOAD_KINDS = tuple(PAYLOAD_KIND_TO_TYPE.keys())


def load_allowed_endpoints(allowlist_path: Path) -> List[Dict[str, Any]]:
    """Làm phẳng allowlist Gateway thành các cặp {method, path, allowed_payload_kinds} cho prompt.

    Đây là danh sách DUY NHẤT agent được chọn. Mọi endpoint khác coi như không tồn tại.
    """
    if not Path(allowlist_path).exists():
        return []
    allowlist = Allowlist.from_json(allowlist_path)

    pairs: List[Dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for rule in allowlist.rules:
        key = (rule.method, rule.path)
        if key in seen:
            continue
        seen.add(key)

        kinds: List[str] = []
        for template_id in rule.allowed_template_ids:
            tmpl = allowlist.templates.get(template_id)
            if (
                tmpl
                and tmpl.method == rule.method
                and tmpl.payload_kind is not None
                and tmpl.payload_kind not in kinds
            ):
                kinds.append(tmpl.payload_kind)

        pairs.append(
            {
                "method": rule.method,
                "path": rule.path,
                "allowed_payload_kinds": kinds,
            }
        )
    return pairs




def _evidence_sort_key(f: Any) -> tuple[str, int, str]:
    """Sap xep theo (file, line, id) de giu dung thu tu bang chung cu.

    Truoc day packet_builder lap group.locations (unique + sorted). Doi
    sang group.findings lam doi thu tu bang chung trong prompt cho moi run
    SAST. Ham nay khoi phuc dung thu tu do.
    """
    if hasattr(f, "location") and f.location is not None:
        file_val = getattr(f.location, "file", "") or ""
        line_val = getattr(f.location, "line", 0) or 0
        id_val = getattr(f, "id", "") or ""
        return (str(file_val), int(line_val), str(id_val))

    if isinstance(f, dict):
        loc = f.get("location")
        if isinstance(loc, dict):
            file_val = loc.get("file") or f.get("file_or_url") or ""
            line_val = loc.get("line") or f.get("line") or 0
        else:
            file_val = f.get("file_or_url") or f.get("file") or ""
            line_val = f.get("line") or 0
        id_val = f.get("id") or ""
        return (str(file_val), int(line_val), str(id_val))

    return ("", 0, str(getattr(f, "id", "")))


def build_analysis_packet(
    group: FindingGroup,
    config: AppConfig,
    project_root: Optional[Path] = None,
    target_root: Optional[Path] = None
) -> AnalysisPacket:
    """Build a complete AnalysisPacket for a finding group without invoking LLM."""
    p_root = project_root or config.project_root
    
    # Determine target_root boundary
    t_root = target_root or config.target_root

    finding_group_dict = group.to_packet_group_dict()

    # Extract source evidence snippets for group locations
    source_evidence_dicts: List[Dict[str, Any]] = []
    limitations: List[str] = []

    seen_evidence_keys: set[tuple[str, int, int]] = set()
    findings_to_process = list(group.findings) if group.findings else []

    if findings_to_process:
        findings_to_process.sort(key=_evidence_sort_key)
        for f in findings_to_process:


            if hasattr(f, "location"):
                f_dict = {
                    "id": getattr(f, "id", ""),
                    "tool": getattr(f, "tool", "") or "opengrep",
                    "file_or_url": getattr(f.location, "file", ""),
                    "line": getattr(f.location, "line", 0),
                    "title": getattr(f, "title", ""),
                    "instances": getattr(f, "instances", []),
                    "instances_total": getattr(f, "instances_total", 0),
                }
            elif isinstance(f, dict):
                f_dict = f
            else:
                f_dict = {}

            sev = evidence_for_finding(

                f_dict,
                project_root=p_root,
                target_root=t_root,
                radius=config.source_radius,
            )
            if sev.error:
                limitations.append(f"Evidence error for {sev.path}: {sev.error}")
            else:
                item = sev.to_evidence_item()
                if item:
                    key = (item.path or "", item.start_line or 0, item.end_line or 0)
                    if key not in seen_evidence_keys:
                        seen_evidence_keys.add(key)
                        source_evidence_dicts.append(item.to_dict())
    else:
        for loc in group.locations:
            sev = extract_source_window(
                project_root=p_root,
                target_root=t_root,
                relative_path=loc.file,
                line=loc.line,
                radius=config.source_radius,
            )
            if sev.error:
                limitations.append(f"Evidence error for {loc.file}:{loc.line}: {sev.error}")
            else:
                item = sev.to_evidence_item()
                if item:
                    key = (item.path or "", item.start_line or 0, item.end_line or 0)
                    if key not in seen_evidence_keys:
                        seen_evidence_keys.add(key)
                        source_evidence_dicts.append(item.to_dict())


    if limitations:
        finding_group_dict["input_limitations"] = limitations

    # Retrieve knowledge hits
    hits = retrieve_knowledge(
        title=group.title,
        rule_id=group.rule_id,
        cwe=group.cwe,
        owasp=group.owasp,
        knowledge_dir=config.knowledge_dir,
        top_k=config.top_k_knowledge,
        max_snippet_chars=config.max_snippet_chars
    )
    knowledge_hits_dicts = [h.to_dict() for h in hits]

    # Load output JSON schema if available
    schema_dict: Dict[str, Any] = {}
    if config.schema_path.exists():
        try:
            schema_dict = json.loads(config.schema_path.read_text(encoding="utf-8"))
        except Exception:
            schema_dict = {}

    return AnalysisPacket(
        group_key=group.group_key,
        task="Analyze this deduplicated scanner-finding group using only the supplied evidence.",
        output_language="vi",
        finding_group=finding_group_dict,
        source_evidence=source_evidence_dicts,
        knowledge_hits=knowledge_hits_dicts,
        output_schema=schema_dict,
        allowed_endpoints=load_allowed_endpoints(config.allowlist_path),
    )
