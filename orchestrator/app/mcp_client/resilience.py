"""Circuit breaker didático (CLOSED/OPEN/HALF_OPEN) para proteger chamadas aos MCP servers.

Implementação própria em vez de uma lib pronta: a lógica de abrir/fechar o circuito
é o diferencial sênior do projeto (tolerância a falhas quando um servidor MCP cai
no meio do raciocínio de um agente), então ela fica explícita e fácil de inspecionar.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Awaitable, Callable, TypeVar

T = TypeVar("T")


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(Exception):
    """O circuito está aberto: a chamada é recusada sem tentar conectar ao MCP server."""


@dataclass
class CircuitBreaker:
    name: str
    failure_threshold: int = 3
    recovery_timeout_s: float = 15.0
    on_open: Callable[[str], None] | None = None
    on_half_open: Callable[[str], None] | None = None
    on_close: Callable[[str], None] | None = None

    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _failure_count: int = field(default=0, init=False)
    _opened_at: float = field(default=0.0, init=False)

    @property
    def state(self) -> CircuitState:
        if self._state is CircuitState.OPEN and (time.monotonic() - self._opened_at) >= self.recovery_timeout_s:
            self._state = CircuitState.HALF_OPEN
            if self.on_half_open:
                self.on_half_open(self.name)
        return self._state

    async def call(self, fn: Callable[[], Awaitable[T]]) -> T:
        if self.state is CircuitState.OPEN:
            raise CircuitOpenError(f"circuit '{self.name}' is open")
        try:
            result = await fn()
        except Exception:
            self._on_failure()
            raise
        self._on_success()
        return result

    def _on_success(self) -> None:
        if self._state is not CircuitState.CLOSED and self.on_close:
            self.on_close(self.name)
        self._state = CircuitState.CLOSED
        self._failure_count = 0

    def _on_failure(self) -> None:
        self._failure_count += 1
        if self._failure_count >= self.failure_threshold and self._state is not CircuitState.OPEN:
            self._state = CircuitState.OPEN
            self._opened_at = time.monotonic()
            if self.on_open:
                self.on_open(self.name)
