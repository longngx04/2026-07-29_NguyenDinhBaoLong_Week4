"""
Analysis coordinator for Security Analysis Agent.
Coordinates packet building, prompt payload hashing, and LLM provider execution with retry handling.
"""

from dataclasses import dataclass
from typing import Optional
from project_sentinel.config import AppConfig
from project_sentinel.analysis.grouping import FindingGroup
from project_sentinel.llm.base import AnalysisPacket, LLMProvider, LLMResult
from project_sentinel.llm.factory import build_llm
from project_sentinel.analysis.packet_builder import build_analysis_packet
from project_sentinel.analysis.prompt_builder import PromptBuilder, PromptPayload


@dataclass
class GroupAnalysisResult:
    """End-to-end analysis result container for a single finding group."""
    group_key: str
    packet: AnalysisPacket
    prompt_payload: PromptPayload
    llm_result: LLMResult


def analyze_finding_group(
    group: FindingGroup,
    config: AppConfig,
    provider: Optional[LLMProvider] = None,
    system_prompt_override: Optional[str] = None
) -> GroupAnalysisResult:
    """Analyze a single deduplicated finding group end-to-end through LLM provider.
    
    Workflow:
    1. Builds deterministic AnalysisPacket (source evidence + knowledge hits).
    2. Builds PromptPayload (system prompt + SHA256 hash).
    3. Invokes LLM provider (provider handles internal bounded retries).
    """
    if provider is None:
        provider = build_llm(config)

    packet = build_analysis_packet(group, config)
    prompt_builder = PromptBuilder()
    prompt_payload = prompt_builder.build(packet, system_prompt_override=system_prompt_override)

    # Call LLM provider (provider handles internal bounded retries)
    result = provider.analyze(packet, system_prompt=prompt_payload.system_prompt)

    return GroupAnalysisResult(
        group_key=group.group_key,
        packet=packet,
        prompt_payload=prompt_payload,
        llm_result=result
    )
