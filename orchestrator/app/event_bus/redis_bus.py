"""Barramento de eventos sobre Redis Pub/Sub.

Cada agente de domínio publica aqui AgentStarted/AgentCompleted/AgentFailed e o
circuit breaker publica ServiceDegraded/ServiceRecovered. O endpoint `/events`
do FastAPI repassa esse stream via SSE para quem quiser observar o raciocínio
distribuído acontecendo em tempo real.
"""
from __future__ import annotations

import logging
from typing import AsyncIterator

import redis.asyncio as redis

from app.config import settings
from mcp_shared.events import EVENT_CHANNEL, OrchestratorEvent, parse_event

logger = logging.getLogger(__name__)

_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.from_url(settings.redis_url, decode_responses=True)
    return _client


async def publish_event(event: OrchestratorEvent) -> None:
    client = get_redis()
    try:
        await client.publish(EVENT_CHANNEL, event.model_dump_json())
    except Exception:
        logger.exception("failed to publish event %s", event.type)


async def subscribe_events() -> AsyncIterator[OrchestratorEvent]:
    client = get_redis()
    pubsub = client.pubsub()
    await pubsub.subscribe(EVENT_CHANNEL)
    try:
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            try:
                yield parse_event(message["data"])
            except ValueError:
                logger.warning("discarding unparseable event: %s", message["data"])
    finally:
        await pubsub.unsubscribe(EVENT_CHANNEL)
        await pubsub.close()
