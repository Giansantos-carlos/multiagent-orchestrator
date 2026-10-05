"""Servidor MCP de Logística — exposto via HTTP (streamable-http) em container próprio."""
from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

mcp = FastMCP(
    "logistics",
    host="0.0.0.0",
    port=int(os.environ.get("PORT", "8001")),
)

# Dados mock. order_id compartilhado com os domínios finance e hr para permitir
# consultas cross-domain coerentes na demo.
_ORDERS = {
    "101": {"status": "shipped", "employee_id": "E01", "sku": "SKU-CAFE-1KG"},
    "102": {"status": "processing", "employee_id": "E02", "sku": "SKU-MOUSE-X"},
    "103": {"status": "delayed", "employee_id": "E03", "sku": "SKU-MONITOR-27"},
}

_STOCK = {
    "SKU-CAFE-1KG": 120,
    "SKU-MOUSE-X": 0,
    "SKU-MONITOR-27": 15,
}


@mcp.tool()
def get_order_status(order_id: str) -> dict:
    """Retorna o status logístico de um pedido (processing/shipped/delivered/delayed)."""
    order = _ORDERS.get(order_id)
    if order is None:
        return {"error": f"order {order_id} not found"}
    return {"order_id": order_id, "status": order["status"], "employee_id": order["employee_id"]}


@mcp.tool()
def check_stock(sku: str) -> dict:
    """Retorna a quantidade disponível em estoque de um SKU."""
    qty = _STOCK.get(sku)
    if qty is None:
        return {"error": f"sku {sku} not found"}
    return {"sku": sku, "quantity_available": qty}


@mcp.tool()
def estimate_delivery(order_id: str) -> dict:
    """Estima dias restantes para entrega de um pedido com base no status atual."""
    order = _ORDERS.get(order_id)
    if order is None:
        return {"error": f"order {order_id} not found"}
    days_by_status = {"processing": 5, "shipped": 2, "delivered": 0, "delayed": 7}
    return {"order_id": order_id, "estimated_days": days_by_status[order["status"]]}


@mcp.custom_route("/health", methods=["GET"])
async def health(_: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "domain": "logistics"})


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
