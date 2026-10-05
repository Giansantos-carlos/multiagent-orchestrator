"""Supervisor: decide quais domínios de negócio a pergunta do usuário toca."""
from __future__ import annotations

from typing import Literal

from langchain_anthropic import ChatAnthropic
from pydantic import BaseModel, Field

from app.config import settings

Domain = Literal["logistics", "finance", "hr"]

_SYSTEM_PROMPT = (
    "Classifique a pergunta do usuário nos domínios de negócio realmente "
    "necessários para respondê-la: 'logistics' (pedidos, estoque, entregas), "
    "'finance' (pagamentos, notas fiscais, limite de crédito), 'hr' "
    "(disponibilidade e férias de funcionários). Retorne apenas os domínios "
    "necessários, nunca todos por padrão."
)


class DomainSelection(BaseModel):
    domains: list[Domain] = Field(description="Domínios de negócio relevantes para responder à pergunta")


async def select_domains(query: str) -> list[Domain]:
    model = ChatAnthropic(model=settings.anthropic_model, api_key=settings.anthropic_api_key)
    structured = model.with_structured_output(DomainSelection)
    result: DomainSelection = await structured.ainvoke(
        [("system", _SYSTEM_PROMPT), ("human", query)]
    )
    return result.domains or ["logistics", "finance", "hr"]
