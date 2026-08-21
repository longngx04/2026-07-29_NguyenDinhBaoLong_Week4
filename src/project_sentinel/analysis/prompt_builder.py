"""
Prompt builder for Security Analysis Agent.
Loads system prompt and builds bounded prompt payloads with SHA256 hash calculation.
"""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from project_sentinel.llm.base import AnalysisPacket, build_packet_dict


@dataclass
class PromptPayload:
    """Bounded prompt payload ready for LLM consumption with provenance hash."""
    system_prompt: str
    packet_dict: Dict[str, Any]
    prompt_sha256: str


class PromptBuilder:
    """Constructs system prompt and formatted AnalysisPacket JSON payload for LLMs."""

    def __init__(self, system_prompt_path: Optional[Path] = None):
        if system_prompt_path is None:
            self.system_prompt_path = (
                Path(__file__).resolve().parents[3]
                / "configs"
                / "prompts"
                / "security-analysis-system.md"
            )
        else:
            self.system_prompt_path = system_prompt_path

    def load_system_prompt(self) -> str:
        """Load system prompt markdown file from disk."""
        if self.system_prompt_path.exists():
            return self.system_prompt_path.read_text(encoding="utf-8").strip()
        raise FileNotFoundError(
            f"Reviewed system prompt not found: {self.system_prompt_path}"
        )

    def build(self, packet: AnalysisPacket, system_prompt_override: Optional[str] = None) -> PromptPayload:
        """Build bounded prompt payload and compute SHA256 hash for run summary provenance."""
        system_prompt = system_prompt_override or self.load_system_prompt()
        packet_dict = build_packet_dict(packet)

        # Deterministic JSON representation for hashing
        json_str = json.dumps(packet_dict, sort_keys=True, ensure_ascii=False)
        combined_text = f"{system_prompt}\n---\n{json_str}"
        prompt_sha256 = hashlib.sha256(combined_text.encode("utf-8")).hexdigest()

        return PromptPayload(
            system_prompt=system_prompt,
            packet_dict=packet_dict,
            prompt_sha256=prompt_sha256
        )


__all__ = ["PromptPayload", "PromptBuilder", "build_packet_dict"]
