"""Servidor MCP Financeiro — exposto via HTTP (streamable-http) em container próprio."""
from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

mcp = FastMCP(
    "finance",
    host="0.0.0.0",
    port=int(os.environ.get("PORT", "8002")),
)

# order_id compartilhado com o domínio logistics para consultas cross-domain.
_PAYMENTS = {
    "101": {"status": "paid", "amount": 89.90, "customer_id": "C01", "invoice_number": "INV-1001"},
    "102": {"status": "pending", "amount": 249.00, "customer_id": "C02", "invoice_number": "INV-1002"},
    "103": {"status": "failed", "amount": 1899.00, "customer_id": "C03", "invoice_number": "INV-1003"},
}

_CREDIT_LIMITS = {
    "C01": {"limit": 5000.0, "used": 320.0},
    "C02": {"limit": 1000.0, "used": 980.0},
    "C03": {"limit": 10000.0, "used": 4500.0},
}


@mcp.tool()
def get_payment_status(order_id: str) -> dict:
    """Retorna o status de pagamento de um pedido (pending/paid/failed/refunded)."""
    payment = _PAYMENTS.get(order_id)
    if payment is None:
        return {"error": f"order {order_id} not found"}
    return {"order_id": order_id, "status": payment["status"], "amount": payment["amount"]}


@mcp.tool()
def get_invoice(order_id: str) -> dict:
    """Retorna o número e valor da nota fiscal associada a um pedido."""
    payment = _PAYMENTS.get(order_id)
    if payment is None:
        return {"error": f"order {order_id} not found"}
    return {
        "order_id": order_id,
        "invoice_number": payment["invoice_number"],
        "amount": payment["amount"],
    }


@mcp.tool()
def check_credit_limit(customer_id: str) -> dict:
    """Retorna limite de crédito total e utilizado de um cliente."""
    credit = _CREDIT_LIMITS.get(customer_id)
    if credit is None:
        return {"error": f"customer {customer_id} not found"}
    return {"customer_id": customer_id, "limit": credit["limit"], "used": credit["used"]}


@mcp.custom_route("/health", methods=["GET"])
async def health(_: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "domain": "finance"})


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
