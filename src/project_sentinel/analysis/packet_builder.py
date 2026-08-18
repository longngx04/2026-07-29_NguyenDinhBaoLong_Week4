"""
Packet builder for Week 3 Security Analysis Agent.
Constructs deterministic AnalysisPacket objects combining deduplicated finding groups,
source evidence snippets, and knowledge retrieval hits.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from project_sentinel.config import AppConfig
from project_sentinel.analysis.evidence import extract_source_window
from project_sentinel.analysis.grouping import FindingGroup
from project_sentinel.llm.base import AnalysisPacket
from project_sentinel.retrieval.knowledge_retriever import retrieve_knowledge


def load_allowed_endpoints(allowlist_path: Path) -> List[Dict[str, str]]:
    """Làm phẳng allowlist Gateway thành các cặp {method, path} cho prompt.

    Đây là danh sách DUY NHẤT agent được chọn. Mọi endpoint khác coi như không tồn tại.
    """
    if not Path(allowlist_path).exists():
        return []
    data = json.loads(Path(allowlist_path).read_text(encoding="utf-8"))
    pairs: List[Dict[str, str]] = []
    for endpoint in data.get("endpoints", []):
        path_value = endpoint.get("path")
        if not path_value:
            continue
        for method in endpoint.get("allowed_methods", []):
            if not method:
                continue
            pair = {"method": str(method).upper(), "path": str(path_value)}
            if pair not in pairs:
                pairs.append(pair)
    return pairs


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

    for loc in group.locations:
        sev = extract_source_window(
            project_root=p_root,
            target_root=t_root,
            relative_path=loc.file,
            line=loc.line,
            radius=config.source_radius
        )
        if sev.error:
            limitations.append(f"Evidence error for {loc.file}:{loc.line}: {sev.error}")
        else:
            item = sev.to_evidence_item()
            if item:
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
