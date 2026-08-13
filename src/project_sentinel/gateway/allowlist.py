from __future__ import annotations
from dataclasses import dataclass
import yaml


@dataclass(frozen=True)
class AllowlistRule:
    method: str
    path: str
    match: str  # "exact" | "prefix"


class Allowlist:
    def __init__(self, rules: list[AllowlistRule]):
        self._rules = rules

    @classmethod
    def from_yaml(cls, path: str) -> "Allowlist":
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        rules = [AllowlistRule(**r) for r in data.get("allowlist", [])]
        if not rules:
            raise ValueError(f"Allowlist rỗng hoặc không hợp lệ: {path}")
        return cls(rules)

    def is_allowed(self, method: str, path: str) -> bool:
        method = method.upper()
        for rule in self._rules:
            if rule.method.upper() != method:
                continue
            if rule.match == "exact" and path == rule.path:
                return True
            if rule.match == "prefix" and path.startswith(rule.path):
                return True
        return False
