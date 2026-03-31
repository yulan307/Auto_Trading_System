from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.execution.models import OrderStatus


class MockBroker:
    def __init__(self) -> None:
        self._orders: dict[str, OrderStatus] = {}

    def place_order(self, order_request):
        if order_request.amount_usd <= 0:
            raise ValueError("amount_usd must be positive")
        if order_request.order_type == "limit" and order_request.price is None:
            raise ValueError("limit order requires price")

        now = datetime.now(timezone.utc)
        order_id = f"mock-{uuid4().hex[:12]}"
        status = OrderStatus(
            order_id=order_id,
            ticker=order_request.ticker,
            side=order_request.side,
            status="submitted",
            submit_time=now,
            update_time=now,
            submitted_price=order_request.price,
            avg_fill_price=None,
            filled_quantity=0.0,
            filled_amount=0.0,
            broker_message="accepted",
        )
        self._orders[order_id] = status
        return status

    def cancel_order(self, order_id: str):
        order = self._orders.get(order_id)
        if order is None:
            return None
        if order.status == "filled":
            return order
        order.status = "canceled"
        order.update_time = datetime.now(timezone.utc)
        return order

    def get_order_status(self, order_id: str):
        return self._orders.get(order_id)
