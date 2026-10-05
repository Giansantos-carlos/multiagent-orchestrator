"""Event schemas trocados no barramento Redis entre orchestrator, agentes e MCP servers."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

EVENT_CHANNEL = "orchestrator.events"

Domain = Literal["logistics", "finance", "hr"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class BaseEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: str
    timestamp: str = Field(default_factory=_now)
    type: str


class AgentStarted(BaseEvent):
    type: Literal["agent_started"] = "agent_started"
    domain: Domain
    task: str


class AgentCompleted(BaseEvent):
    type: Literal["agent_completed"] = "agent_completed"
    domain: Domain
    result_summary: str
    latency_ms: float


class AgentFailed(BaseEvent):
    type: Literal["agent_failed"] = "agent_failed"
    domain: Domain
    error: str


class ServiceDegraded(BaseEvent):
    type: Literal["service_degraded"] = "service_degraded"
    domain: Domain
    reason: str
    circuit_state: Literal["open", "half_open"]


class ServiceRecovered(BaseEvent):
    type: Literal["service_recovered"] = "service_recovered"
    domain: Domain


OrchestratorEvent = (
    AgentStarted | AgentCompleted | AgentFailed | ServiceDegraded | ServiceRecovered
)


def parse_event(raw: str) -> OrchestratorEvent:
    import json

    data = json.loads(raw)
    event_type = data.get("type")
    mapping: dict[str, type[BaseEvent]] = {
        "agent_started": AgentStarted,
        "agent_completed": AgentCompleted,
        "agent_failed": AgentFailed,
        "service_degraded": ServiceDegraded,
        "service_recovered": ServiceRecovered,
    }
    model = mapping.get(event_type)
    if model is None:
        raise ValueError(f"Unknown event type: {event_type}")
    return model.model_validate(data)
