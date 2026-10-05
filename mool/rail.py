"""A local mock UPI rail. Each credit is announced like a merchant soundbox."""
from __future__ import annotations
import itertools
from dataclasses import dataclass, field


@dataclass
class Credit:
    txn_id: str
    upi: str
    amount: int
    memo: str

    @property
    def soundbox(self) -> str:
        return f"{self.upi}: ₹{self.amount} received"


@dataclass
class MockUPIRail:
    ledger: list = field(default_factory=list)
    _ids: itertools.count = field(default_factory=lambda: itertools.count(1))

    def pay(self, upi: str, amount: int, memo: str = "") -> Credit:
        credit = Credit(f"MOOLTXN{next(self._ids):06d}", upi, int(amount), memo)
        self.ledger.append(credit)
        return credit
