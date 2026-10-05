"""Checkpointer Redis para o estado distribuído do grafo LangGraph.

Cada superstep do grafo (supervisor -> agentes de domínio -> aggregator) é
persistido no Redis. Se o processo do orchestrator reiniciar no meio de uma
execução, o grafo pode retomar do último checkpoint em vez de recomeçar do
zero — essa é a peça de "gerenciamento de estado distribuído" do projeto.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from langgraph.checkpoint.redis import AsyncRedisSaver

from app.config import settings


@asynccontextmanager
async def redis_checkpointer() -> AsyncIterator[AsyncRedisSaver]:
    async with AsyncRedisSaver.from_conn_string(settings.redis_url) as saver:
        await saver.asetup()
        yield saver
