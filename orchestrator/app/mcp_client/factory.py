"""Fábrica de sessões MCP por domínio, com circuit breaker e retry/backoff."""
from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Callable

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from app.config import settings
from app.mcp_client.resilience import CircuitBreaker

logger = logging.getLogger(__name__)

_BREAKERS: dict[str, CircuitBreaker] = {}


def get_breaker(
    domain: str,
    *,
    on_open: Callable[[str], None] | None = None,
    on_half_open: Callable[[str], None] | None = None,
    on_close: Callable[[str], None] | None = None,
) -> CircuitBreaker:
    breaker = _BREAKERS.get(domain)
    if breaker is None:
        breaker = CircuitBreaker(
            name=domain,
            failure_threshold=settings.circuit_failure_threshold,
            recovery_timeout_s=settings.circuit_recovery_timeout_s,
            on_open=on_open,
            on_half_open=on_half_open,
            on_close=on_close,
        )
        _BREAKERS[domain] = breaker
    return breaker


@asynccontextmanager
async def mcp_session(url: str) -> AsyncIterator[ClientSession]:
    async with streamablehttp_client(url, timeout=settings.mcp_timeout_s) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


def _extract_payload(result: Any) -> dict:
    if result.content:
        first = result.content[0]
        text = getattr(first, "text", None)
        if text is not None:
            return json.loads(text)
    return {"error": "empty response from mcp server"}


async def call_tool(
    domain: str,
    tool_name: str,
    arguments: dict[str, Any],
    *,
    on_open: Callable[[str], None] | None = None,
    on_half_open: Callable[[str], None] | None = None,
    on_close: Callable[[str], None] | None = None,
) -> dict:
    """Chama uma tool MCP de um domínio protegida por circuit breaker + retry com backoff.

    Se o circuito estiver aberto (domínio marcado indisponível), levanta
    `CircuitOpenError` imediatamente, sem tentar conectar — o domain_agent decide
    como degradar graciosamente a partir daí.
    """
    breaker = get_breaker(domain, on_open=on_open, on_half_open=on_half_open, on_close=on_close)
    url = settings.mcp_urls[domain]

    async def _attempt() -> dict:
        async with mcp_session(url) as session:
            result = await session.call_tool(tool_name, arguments)
            return _extract_payload(result)

    async def _with_retry() -> dict:
        last_exc: Exception | None = None
        for attempt in range(settings.mcp_retry_attempts):
            try:
                return await _attempt()
            except Exception as exc:  # conexão recusada, timeout, servidor fora do ar
                last_exc = exc
                logger.warning(
                    "mcp call failed domain=%s tool=%s attempt=%d/%d: %s",
                    domain,
                    tool_name,
                    attempt + 1,
                    settings.mcp_retry_attempts,
                    exc,
                )
                if attempt < settings.mcp_retry_attempts - 1:
                    await asyncio.sleep(settings.mcp_retry_base_delay_s * (2**attempt))
        assert last_exc is not None
        raise last_exc

    return await breaker.call(_with_retry)
