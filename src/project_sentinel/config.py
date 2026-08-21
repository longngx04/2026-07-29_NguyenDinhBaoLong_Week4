"""
Configuration management for Project Sentinel Security Analysis Agent.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional


def _project_root() -> Path:
    """Resolve the repository root from this file's location (src/project_sentinel/config.py)."""
    return Path(__file__).resolve().parent.parent.parent


def _load_dotenv(dotenv_path: Optional[Path] = None) -> None:
    if dotenv_path is None:
        dotenv_path = _project_root() / ".env"
    if not dotenv_path.exists():
        return
    try:
        for line in dotenv_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip("'\"")
            if key and key not in os.environ:
                os.environ[key] = val
    except OSError:
        pass  # .env missing or unreadable — optional file


@dataclass
class AppConfig:
    """Application configuration for the analysis pipeline."""
    
    # Paths
    project_root: Path = field(default_factory=_project_root)
    knowledge_dir: Path = field(default_factory=lambda: _project_root() / "data" / "knowledge-base")
    schema_path: Path = field(default_factory=lambda: _project_root() / "schemas" / "security-analysis-record.schema.json")
    allowlist_path: Path = field(default_factory=lambda: _project_root() / "configs" / "gateway" / "endpoint-allowlist.json")
    input_findings_path: Path = field(default_factory=lambda: _project_root() / "artifacts" / "normalized" / "findings.json")
    output_jsonl_path: Path = field(default_factory=lambda: _project_root() / "artifacts" / "analysis" / "security-analysis.jsonl")
    summary_path: Path = field(default_factory=lambda: _project_root() / "artifacts" / "analysis" / "run-summary.json")
    target_root: Path = field(default_factory=lambda: _project_root() / "benchmarks" / "targets" / "webgoat")
    
    # LLM Settings
    provider_type: str = field(default_factory=lambda: os.getenv("LLM_PROVIDER", "openrouter"))
    # Mac dinh phai khop .env.example: moi so lieu trong reports/week-06/ deu
    # sinh boi model nay. Mot mac dinh khac lam nguoi clone repo theo README
    # khong tai lap duoc ket qua da cong bo.
    model_name: str = field(
        default_factory=lambda: os.getenv("LLM_MODEL", "qwen/qwen3-235b-a22b-2507")
    )
    api_key: str = field(default_factory=lambda: os.getenv("LLM_API_KEY", ""))
    base_url: str = field(default_factory=lambda: os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1"))
    timeout: float = field(default_factory=lambda: float(
        os.getenv("LLM_TIMEOUT_SECONDS", os.getenv("LLM_TIMEOUT", "60"))
    ))
    max_retries: int = field(default_factory=lambda: int(os.getenv("LLM_MAX_RETRIES", "1")))
    # Number of finding groups analyzed concurrently. Groups are independent and
    # results are reassembled in input order, so this changes runtime only.
    llm_concurrency: int = field(default_factory=lambda: max(1, int(os.getenv("LLM_CONCURRENCY", "4"))))
    validation_max_retries: int = field(default_factory=lambda: int(os.getenv("VALIDATION_MAX_RETRIES", "1")))
    
    # Analysis Limits & Parameters
    top_k_knowledge: int = 3
    # 28 dong moi ben, khong phai 4. Do tren 23 finding WebGoat that:
    # radius=4 khong với tới annotation @PostMapping/@RequestParam cua BAT KY
    # true positive nao (0/13), nen Agent khong the chung minh attacker control
    # va tra not_proven cho ca nhung ca hien nhien nhat. radius=28 với tới 12/13,
    # va bao hoa sau do. Java dat annotation phia tren chu ky ham nen cua so hep
    # luon hut phan quan trong nhat.
    source_radius: int = 28  # lines around finding line
    max_snippet_chars: int = 700
    # TAT mac dinh (-1). Gom trung that su da do khoa (rule, file, dong) lo, nen
    # proximity merge theo dinh nghia chi gop duoc cac DONG KHAC NHAU — tuc luon
    # gop hai sink khac nhau. Tren WebGoat no gop
    #   SqlInjectionLesson3.java:47  executeUpdate(query)         <- lo hong that
    #   SqlInjectionLesson3.java:49  executeQuery("...Barnett;")  <- truy van hang
    # Schema chi cho MOT disposition moi nhom, nen false positive thua huong
    # confirmed/high cua true positive nam canh. Do la nguyen nhan truc tiep cua
    # over-claim 33,3%, khong phai loi phan doan cua Agent.
    # Dat >= 0 de bat lai neu that su can.
    near_dup_line_threshold: int = -1

    def ensure_openrouter_ready(self) -> None:
        """Ensure OpenRouter configuration is valid before attempting network requests."""
        if not self.api_key.strip():
            raise ValueError("LLM_API_KEY is required for OpenRouter")
        if not self.base_url.startswith("https://"):
            raise ValueError("LLM_BASE_URL must be an HTTPS URL")

    @classmethod
    def from_env(
        cls,
        dotenv_path: Optional[Path] = None,
        input_findings_path: Optional[Path] = None,
        output_jsonl_path: Optional[Path] = None,
        summary_path: Optional[Path] = None,
        provider_type: Optional[str] = None,
        knowledge_dir: Optional[Path] = None,
        target_root: Optional[Path] = None,
        validation_max_retries: Optional[int] = None
    ) -> "AppConfig":
        """Factory method creating AppConfig instance from environment variables and CLI overrides."""
        _load_dotenv(dotenv_path=dotenv_path)
        # Chua ca Path, str, int va float — khong phai chi Path.
        kwargs: Dict[str, Any] = {}
        if input_findings_path is not None:
            kwargs["input_findings_path"] = input_findings_path
        if output_jsonl_path is not None:
            kwargs["output_jsonl_path"] = output_jsonl_path
        if summary_path is not None:
            kwargs["summary_path"] = summary_path
        if provider_type is not None:
            kwargs["provider_type"] = provider_type
        if knowledge_dir is not None:
            kwargs["knowledge_dir"] = knowledge_dir
        if target_root is not None:
            kwargs["target_root"] = target_root
        if validation_max_retries is not None:
            kwargs["validation_max_retries"] = validation_max_retries
        return cls(**kwargs)
