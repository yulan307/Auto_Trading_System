from __future__ import annotations


class IBAccountManager:
    def connect(self) -> None:
        raise NotImplementedError("IB account integration is reserved for a later phase.")
