"""Configuração do orchestrator via variáveis de ambiente."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


@dataclass(frozen=True)
class Settings:
    anthropic_api_key: str = field(default_factory=lambda: os.environ.get("ANTHROPIC_API_KEY", ""))
    anthropic_model: str = field(default_factory=lambda: _env("ANTHROPIC_MODEL", "claude-sonnet-5"))

    redis_url: str = field(default_factory=lambda: _env("REDIS_URL", "redis://redis:6379/0"))

    mcp_urls: dict[str, str] = field(
        default_factory=lambda: {
            "logistics": _env("MCP_LOGISTICS_URL", "http://mcp-logistics:8001/mcp"),
            "finance": _env("MCP_FINANCE_URL", "http://mcp-finance:8002/mcp"),
            "hr": _env("MCP_HR_URL", "http://mcp-hr:8003/mcp"),
        }
    )

    mcp_timeout_s: float = field(default_factory=lambda: float(_env("MCP_TIMEOUT_S", "5")))
    mcp_retry_attempts: int = field(default_factory=lambda: int(_env("MCP_RETRY_ATTEMPTS", "3")))
    mcp_retry_base_delay_s: float = field(default_factory=lambda: float(_env("MCP_RETRY_BASE_DELAY_S", "0.3")))

    circuit_failure_threshold: int = field(default_factory=lambda: int(_env("CIRCUIT_FAILURE_THRESHOLD", "3")))
    circuit_recovery_timeout_s: float = field(default_factory=lambda: float(_env("CIRCUIT_RECOVERY_TIMEOUT_S", "15")))


settings = Settings()
