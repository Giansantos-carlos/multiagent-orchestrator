"""Agente de domínio genérico: ReAct agent (LLM + tools MCP) especializado em um domínio.

Cada domínio (logistics/finance/hr) roda o mesmo padrão de agente, parametrizado
pelas tools daquele domínio. Se o circuito daquele domínio estiver aberto (MCP
server fora do ar), o agente devolve uma resposta degradada em vez de propagar
o erro para o resto do grafo — é isso que permite ao orchestrator responder
parcialmente mesmo com um domínio indisponível.
"""
from __future__ import annotations

import asyncio
import time
from typing import Literal

from langchain_anthropic import ChatAnthropic
from langgraph.prebuilt import ToolNode, create_react_agent

from app.agents import tool_specs
from app.config import settings
from app.event_bus.redis_bus import publish_event
from app.mcp_client.resilience import CircuitOpenError
from mcp_shared.events import (
    AgentCompleted,
    AgentFailed,
    AgentStarted,
    ServiceDegraded,
    ServiceRecovered,
)

Domain = Literal["logistics", "finance", "hr"]

_TOOL_BUILDERS = {
    "logistics": tool_specs.build_logistics_tools,
    "finance": tool_specs.build_finance_tools,
    "hr": tool_specs.build_hr_tools,
}

_SYSTEM_PROMPTS = {
    "logistics": "Você é o agente especialista em Logística. Use as tools disponíveis e responda em português de forma objetiva.",
    "finance": "Você é o agente especialista em Financeiro. Use as tools disponíveis e responda em português de forma objetiva.",
    "hr": "Você é o agente especialista em RH. Use as tools disponíveis e responda em português de forma objetiva.",
}


def _fire(coro) -> None:
    """Publica um evento sem bloquear o callback síncrono do circuit breaker."""
    asyncio.create_task(coro)


async def run_domain_agent(domain: Domain, query: str, correlation_id: str) -> dict:
    started = time.monotonic()
    await publish_event(AgentStarted(correlation_id=correlation_id, domain=domain, task=query))

    def on_open(_name: str) -> None:
        _fire(
            publish_event(
                ServiceDegraded(
                    correlation_id=correlation_id,
                    domain=domain,
                    reason="limite de falhas consecutivas excedido",
                    circuit_state="open",
                )
            )
        )

    def on_half_open(_name: str) -> None:
        _fire(
            publish_event(
                ServiceDegraded(
                    correlation_id=correlation_id,
                    domain=domain,
                    reason="testando recuperação do serviço",
                    circuit_state="half_open",
                )
            )
        )

    def on_close(_name: str) -> None:
        _fire(publish_event(ServiceRecovered(correlation_id=correlation_id, domain=domain)))

    tools = _TOOL_BUILDERS[domain](on_open=on_open, on_half_open=on_half_open, on_close=on_close)
    model = ChatAnthropic(model=settings.anthropic_model, api_key=settings.anthropic_api_key)
    agent = create_react_agent(model, tools=ToolNode(tools, handle_tool_errors=False))

    try:
        response = await agent.ainvoke(
            {"messages": [("system", _SYSTEM_PROMPTS[domain]), ("human", query)]},
            config={"recursion_limit": 8},
        )
        answer = response["messages"][-1].content
        latency_ms = (time.monotonic() - started) * 1000
        await publish_event(
            AgentCompleted(
                correlation_id=correlation_id,
                domain=domain,
                result_summary=str(answer)[:200],
                latency_ms=latency_ms,
            )
        )
        return {"domain": domain, "status": "ok", "answer": answer}
    except CircuitOpenError as exc:
        await publish_event(AgentFailed(correlation_id=correlation_id, domain=domain, error=str(exc)))
        return {
            "domain": domain,
            "status": "degraded",
            "answer": f"Domínio {domain} está indisponível no momento (circuito aberto após falhas repetidas).",
        }
    except Exception as exc:  # erro inesperado do agente/LLM/tool
        await publish_event(AgentFailed(correlation_id=correlation_id, domain=domain, error=str(exc)))
        return {"domain": domain, "status": "error", "answer": f"Falha ao consultar o domínio {domain}: {exc}"}
