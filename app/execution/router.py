from __future__ import annotations


class BaseBroker:
    def place_order(self, order_request):
        raise NotImplementedError

    def cancel_order(self, order_id: str):
        raise NotImplementedError

    def get_order_status(self, order_id: str):
        raise NotImplementedError


class ExecutionEngine:
    def __init__(self, broker: BaseBroker) -> None:
        self.broker = broker

    def submit_order(self, order_request):
        return self.broker.place_order(order_request)

    def cancel_order(self, order_id: str):
        return self.broker.cancel_order(order_id)

    def get_order_status(self, order_id: str):
        return self.broker.get_order_status(order_id)
