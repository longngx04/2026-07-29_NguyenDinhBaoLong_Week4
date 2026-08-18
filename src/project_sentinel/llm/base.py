"""
Base contract definitions for LLM Providers in Project Sentinel.
"""

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable
from dataclasses import dataclass, field


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
