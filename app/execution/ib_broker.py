from __future__ import annotations


class IBBroker:
    def place_order(self, order_request):
        raise NotImplementedError("IB broker integration is reserved for a later phase.")
