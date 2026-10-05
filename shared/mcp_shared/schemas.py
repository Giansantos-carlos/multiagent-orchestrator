"""DTOs trocados entre os MCP servers de domínio e os agentes do orchestrator."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

# Chave comum usada nos dados mock dos 3 domínios para permitir consultas
# cross-domain coerentes na demo: cada pedido tem um pagamento e um
# funcionário responsável associados pelo mesmo order_id.

ORDER_IDS = ("101", "102", "103")


class OrderStatus(BaseModel):
    order_id: str
    status: Literal["processing", "shipped", "delivered", "delayed"]
    employee_id: str


class StockItem(BaseModel):
    sku: str
    quantity_available: int


class DeliveryEstimate(BaseModel):
    order_id: str
    estimated_days: int


class PaymentStatus(BaseModel):
    order_id: str
    status: Literal["pending", "paid", "failed", "refunded"]
    amount: float


class Invoice(BaseModel):
    order_id: str
    invoice_number: str
    amount: float


class CreditLimit(BaseModel):
    customer_id: str
    limit: float
    used: float


class EmployeeAvailability(BaseModel):
    employee_id: str
    name: str
    available: bool


class TimeOffStatus(BaseModel):
    employee_id: str
    on_leave: bool
    return_date: str | None = None
