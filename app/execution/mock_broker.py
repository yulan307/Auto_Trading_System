from __future__ import annotations


class MockBroker:
    def place_order(self, order_request):
        raise NotImplementedError("Mock broker will be implemented in phase 6.")

    def cancel_order(self, order_id: str):
        raise NotImplementedError("Mock broker will be implemented in phase 6.")

    def get_order_status(self, order_id: str):
        raise NotImplementedError("Mock broker will be implemented in phase 6.")
