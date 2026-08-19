"""
Base contract definitions for LLM Providers in Project Sentinel.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from project_sentinel.guardrails.injection import wrap_untrusted


@dataclass
class AnalysisPacket:
    """Input packet sent to an LLM provider for analyzing a finding group."""
    group_key: str
    task: str = "Analyze this deduplicated scanner-finding group using only the supplied evidence."
    output_language: str = "vi"
    finding_group: Dict[str, Any] = field(default_factory=dict)
    source_evidence: List[Dict[str, Any]] = field(default_factory=list)
    knowledge_hits: List[Dict[str, Any]] = field(default_factory=list)
    output_schema: Dict[str, Any] = field(default_factory=dict)
    allowed_endpoints: List[Dict[str, Any]] = field(default_factory=list)


def build_packet_dict(packet: AnalysisPacket) -> Dict[str, Any]:
    """Payload user message. DUY NHẤT một nơi dựng nó."""
    wrapped_source_evidence: List[Dict[str, Any]] = []
    for ev in (packet.source_evidence or []):
        if isinstance(ev, dict) and "content" in ev and isinstance(ev["content"], str):
            wrapped_ev = dict(ev)
            wrapped_ev["content"] = wrap_untrusted(ev["content"])
            wrapped_source_evidence.append(wrapped_ev)
        else:
            wrapped_source_evidence.append(ev)

    return {
        "task": packet.task,
        "output_language": packet.output_language,
        "group_key": packet.group_key,
        "finding_group": packet.finding_group,
        "source_evidence": wrapped_source_evidence,
        "knowledge_hits": packet.knowledge_hits,
        "allowed_endpoints": packet.allowed_endpoints,
        "output_schema": packet.output_schema,
    }


@dataclass
class LLMResult:
    """Result returned by an LLM provider."""
    raw_response: str
    parsed_response: Optional[Dict[str, Any]] = None
    model_name: str = "unknown"
    request_id: Optional[str] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    latency_ms: float = 0.0
    error: Optional[str] = None


@runtime_checkable
class LLMProvider(Protocol):
    """Protocol defining the LLM Provider interface contract."""
    
    def analyze(self, packet: AnalysisPacket, system_prompt: Optional[str] = None) -> LLMResult:
        """Analyze a finding group packet and return an LLMResult."""
        ...

    def generate(self, *, system_prompt: str, user_prompt: str) -> LLMResult:
        """Generate one structured JSON response from explicit system and user prompts."""
        ...
