from __future__ import annotations


class BaseBroker:
    def place_order(self, order_request):
        raise NotImplementedError

    def cancel_order(self, order_id: str):
        raise NotImplementedError

    def get_order_status(self, order_id: str):
        raise NotImplementedError
