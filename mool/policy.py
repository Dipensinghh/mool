"""The policy at the pay() sink. Never reads text; only checks where values came from."""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum

from .provenance import Tagged, Trust
from .world import UPI_CIRCLE_PER_TXN_CAP, contact_by_upi


class Verdict(str, Enum):
    ALLOW = "allow"
    HOLD = "hold"   # ask the human, in their language, before any money moves


@dataclass
class Decision:
    verdict: Verdict
    reasons: list = field(default_factory=list)
    question: str | None = None


def check_payment(payee: Tagged, amount: Tagged) -> Decision:
    reasons: list[str] = []

    # Rule 1: the payee must trace to the user's words, saved contacts or a verified registry.
    if not payee.trusted:
        untrusted = [o.source for o in payee.origins if o.trust == Trust.UNTRUSTED]
        return Decision(Verdict.HOLD,
                        [f"payee {payee.value} came from {', '.join(sorted(untrusted))}, not from you or your contacts"],
                        f"Pay {payee.value}? This UPI ID came from a document, not from your contacts.")
    contact = contact_by_upi(str(payee.value))
    reasons.append(f"payee traces to {', '.join(payee.sources)}")

    amt = int(amount.value) if isinstance(amount.value, (int, float)) else -1
    if amt <= 0:
        return Decision(Verdict.HOLD, reasons + ["no valid amount"], "How much should I pay?")
    if amt > UPI_CIRCLE_PER_TXN_CAP:
        return Decision(Verdict.HOLD, reasons + [f"₹{amt} is above the ₹{UPI_CIRCLE_PER_TXN_CAP} delegation cap"],
                        f"₹{amt} is above your agent limit. Pay it yourself?")

    # Rule 2: an amount from untrusted text must sit inside a bound the user or past bills set.
    if amount.trusted:
        reasons.append(f"amount ₹{amt} came from {', '.join(amount.sources)}")
    else:
        bound = contact.amount_bound if contact else 0
        if amt > bound:
            name = contact.name if contact else str(payee.value)
            return Decision(Verdict.HOLD,
                            reasons + [f"amount ₹{amt} came from a document and exceeds the ₹{bound} bound for {name}"],
                            f"{name}'s bill says ₹{amt}. That's more than usual. Pay it?")
        reasons.append(f"amount ₹{amt} from document is inside the ₹{bound} bound")

    return Decision(Verdict.ALLOW, reasons)
