"""API do orchestrator: dispara consultas cross-domain e expõe o stream de eventos."""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.event_bus.redis_bus import subscribe_events
from app.graph import build_graph
from app.state.checkpointer import redis_checkpointer

app_state: dict = {}


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    async with redis_checkpointer() as checkpointer:
        app_state["graph"] = build_graph(checkpointer)
        yield
    app_state.clear()


app = FastAPI(title="Multiagent Orchestrator", lifespan=lifespan)


class QueryRequest(BaseModel):
    text: str


class QueryResponse(BaseModel):
    correlation_id: str
    answer: str
    domains: list[str]


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest) -> QueryResponse:
    correlation_id = str(uuid.uuid4())
    graph = app_state["graph"]
    result = await graph.ainvoke(
        {"correlation_id": correlation_id, "query": request.text, "results": {}},
        config={"configurable": {"thread_id": correlation_id}},
    )
    return QueryResponse(
        correlation_id=correlation_id,
        answer=result["final_answer"],
        domains=result.get("domains", []),
    )


@app.get("/events")
async def events() -> StreamingResponse:
    async def _stream() -> AsyncIterator[str]:
        async for event in subscribe_events():
            yield f"data: {event.model_dump_json()}\n\n"

    return StreamingResponse(_stream(), media_type="text/event-stream")
