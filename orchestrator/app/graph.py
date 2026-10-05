"""Grafo LangGraph: supervisor -> fan-out para agentes de domínio -> aggregator.

O estado é persistido a cada superstep pelo checkpointer Redis (ver
`app/state/checkpointer.py`), permitindo retomar a execução caso o processo
do orchestrator reinicie no meio de uma consulta cross-domain.
"""
from __future__ import annotations

from typing import Annotated, Literal, TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Send

from app.agents.aggregator import aggregate
from app.agents.domain_agent import run_domain_agent
from app.agents.supervisor import select_domains

Domain = Literal["logistics", "finance", "hr"]


def _merge_results(left: dict, right: dict) -> dict:
    merged = dict(left)
    merged.update(right)
    return merged


class OrchestratorState(TypedDict):
    correlation_id: str
    query: str
    domains: list[Domain]
    results: Annotated[dict[str, dict], _merge_results]
    final_answer: str


class DomainTask(TypedDict):
    domain: Domain
    query: str
    correlation_id: str


async def supervisor_node(state: OrchestratorState) -> dict:
    domains = await select_domains(state["query"])
    return {"domains": domains}


def fan_out(state: OrchestratorState) -> list[Send]:
    return [
        Send(
            "domain_agent",
            {"domain": domain, "query": state["query"], "correlation_id": state["correlation_id"]},
        )
        for domain in state["domains"]
    ]


async def domain_agent_node(payload: DomainTask) -> dict:
    result = await run_domain_agent(payload["domain"], payload["query"], payload["correlation_id"])
    return {"results": {result["domain"]: result}}


async def aggregator_node(state: OrchestratorState) -> dict:
    return {"final_answer": aggregate(state["results"])}


def build_graph(checkpointer: BaseCheckpointSaver | None = None) -> CompiledStateGraph:
    graph = StateGraph(OrchestratorState)
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("domain_agent", domain_agent_node)
    graph.add_node("aggregator", aggregator_node)

    graph.add_edge(START, "supervisor")
    graph.add_conditional_edges("supervisor", fan_out, ["domain_agent"])
    graph.add_edge("domain_agent", "aggregator")
    graph.add_edge("aggregator", END)

    return graph.compile(checkpointer=checkpointer)
