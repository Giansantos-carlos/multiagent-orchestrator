"""Servidor MCP de RH — exposto via HTTP (streamable-http) em container próprio."""
from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

mcp = FastMCP(
    "hr",
    host="0.0.0.0",
    port=int(os.environ.get("PORT", "8003")),
)

# employee_id compartilhado com o domínio logistics (employee_id por order_id)
# para permitir consultas cross-domain coerentes na demo.
_EMPLOYEES = {
    "E01": {"name": "Ana Souza", "available": True, "on_leave": False, "return_date": None},
    "E02": {"name": "Bruno Lima", "available": False, "on_leave": True, "return_date": "2026-10-10"},
    "E03": {"name": "Carla Dias", "available": True, "on_leave": False, "return_date": None},
}

_ORDER_TO_EMPLOYEE = {"101": "E01", "102": "E02", "103": "E03"}


@mcp.tool()
def get_employee_availability(employee_id: str) -> dict:
    """Retorna se um funcionário está disponível no momento."""
    employee = _EMPLOYEES.get(employee_id)
    if employee is None:
        return {"error": f"employee {employee_id} not found"}
    return {
        "employee_id": employee_id,
        "name": employee["name"],
        "available": employee["available"],
    }


@mcp.tool()
def get_employee_by_order(order_id: str) -> dict:
    """Retorna o funcionário responsável por um pedido."""
    employee_id = _ORDER_TO_EMPLOYEE.get(order_id)
    if employee_id is None:
        return {"error": f"order {order_id} not found"}
    return {"order_id": order_id, "employee_id": employee_id}


@mcp.tool()
def request_time_off_status(employee_id: str) -> dict:
    """Retorna se o funcionário está de férias/licença e a data de retorno prevista."""
    employee = _EMPLOYEES.get(employee_id)
    if employee is None:
        return {"error": f"employee {employee_id} not found"}
    return {
        "employee_id": employee_id,
        "on_leave": employee["on_leave"],
        "return_date": employee["return_date"],
    }


@mcp.custom_route("/health", methods=["GET"])
async def health(_: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "domain": "hr"})


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
