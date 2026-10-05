"""Tools LangChain por domínio.

Cada tool chama `app.mcp_client.factory.call_tool`, que abre uma sessão MCP
HTTP nova por chamada contra o servidor remoto do domínio e passa pelo
circuit breaker + retry — é assim que o agente de domínio "conversa" com o
servidor MCP distribuído com tolerância a falhas.
"""
from __future__ import annotations

from typing import Callable

from langchain_core.tools import tool

from app.mcp_client.factory import call_tool

Hook = Callable[[str], None] | None


def build_logistics_tools(on_open: Hook = None, on_half_open: Hook = None, on_close: Hook = None) -> list:
    hooks = dict(on_open=on_open, on_half_open=on_half_open, on_close=on_close)

    @tool
    async def get_order_status(order_id: str) -> dict:
        """Status logístico de um pedido: processing, shipped, delivered ou delayed."""
        return await call_tool("logistics", "get_order_status", {"order_id": order_id}, **hooks)

    @tool
    async def check_stock(sku: str) -> dict:
        """Quantidade disponível em estoque de um SKU."""
        return await call_tool("logistics", "check_stock", {"sku": sku}, **hooks)

    @tool
    async def estimate_delivery(order_id: str) -> dict:
        """Estimativa de dias restantes para entrega de um pedido."""
        return await call_tool("logistics", "estimate_delivery", {"order_id": order_id}, **hooks)

    return [get_order_status, check_stock, estimate_delivery]


def build_finance_tools(on_open: Hook = None, on_half_open: Hook = None, on_close: Hook = None) -> list:
    hooks = dict(on_open=on_open, on_half_open=on_half_open, on_close=on_close)

    @tool
    async def get_payment_status(order_id: str) -> dict:
        """Status de pagamento de um pedido: pending, paid, failed ou refunded."""
        return await call_tool("finance", "get_payment_status", {"order_id": order_id}, **hooks)

    @tool
    async def get_invoice(order_id: str) -> dict:
        """Número e valor da nota fiscal associada a um pedido."""
        return await call_tool("finance", "get_invoice", {"order_id": order_id}, **hooks)

    @tool
    async def check_credit_limit(customer_id: str) -> dict:
        """Limite de crédito total e utilizado de um cliente."""
        return await call_tool("finance", "check_credit_limit", {"customer_id": customer_id}, **hooks)

    return [get_payment_status, get_invoice, check_credit_limit]


def build_hr_tools(on_open: Hook = None, on_half_open: Hook = None, on_close: Hook = None) -> list:
    hooks = dict(on_open=on_open, on_half_open=on_half_open, on_close=on_close)

    @tool
    async def get_employee_availability(employee_id: str) -> dict:
        """Se um funcionário está disponível no momento."""
        return await call_tool("hr", "get_employee_availability", {"employee_id": employee_id}, **hooks)

    @tool
    async def get_employee_by_order(order_id: str) -> dict:
        """Funcionário responsável por um pedido."""
        return await call_tool("hr", "get_employee_by_order", {"order_id": order_id}, **hooks)

    @tool
    async def request_time_off_status(employee_id: str) -> dict:
        """Se o funcionário está de férias/licença e a data de retorno prevista."""
        return await call_tool("hr", "request_time_off_status", {"employee_id": employee_id}, **hooks)

    return [get_employee_availability, get_employee_by_order, request_time_off_status]
