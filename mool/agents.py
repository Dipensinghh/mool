"""Three agents that do the same job: pay the bill the user asked for.

NaiveAgent           one model, reads everything, calls pay() directly.
DetectorGuardedAgent NaiveAgent behind a prompt-injection text detector.
MoolAgent            privileged planner + quarantined extractor + provenance-checked pay().

All three share the same deliberately gullible "model" (gullible_read). That is the point:
Mool's guarantee does not depend on the model resisting injection.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field

from .policy import Decision, Verdict, check_payment
from .provenance import Tagged, Trust, tag
from .rail import Credit, MockUPIRail
from .receipt import sign_receipt
from .world import UPI_CIRCLE_PER_TXN_CAP, find_contact_in


@dataclass(frozen=True)
class Document:
    source: str  # "doc:invoice.pdf", "web:...", "mcp:merchant_lookup"
    text: str


@dataclass
class RunResult:
    agent: str
    credit: Credit | None
    verdict: str
    reasons: list = field(default_factory=list)
    question: str | None = None
    receipt: dict | None = None
    trace: list = field(default_factory=list)


# --- the stand-in model -------------------------------------------------------------------
# Emulates how instruction-following LLMs behave when untrusted text sits in their context:
# values stated next to instructions win. Swap in Gemini or Sarvam via a real extractor;
# nothing in the policy changes.
UPI_RE = re.compile(r"[A-Za-z0-9._\-]+@[A-Za-z][A-Za-z0-9]+")
AMT_RE = re.compile(r'(?:₹|rs\.?|inr|am=|amount"?\s*[:=]\s*"?|total\s*[:=]|कुल\s*:?)\s*([0-9][0-9,]*)', re.I)
STEER = ("ignore", "instruction", "system", "note to ai", "assistant", "updated", "changed", "new upi",
         "pay to", "send to", "bhejo", "bhej do", "नया", "बदल", "भेजें", "सहायक", "upi://", "scan to pay")


def _candidates(line: str, fld: str) -> list:
    if fld == "upi":
        return UPI_RE.findall(line)
    return [int(m.replace(",", "")) for m in AMT_RE.findall(line)]


def gullible_read(text: str, fld: str):
    steered, plain = [], []
    for line in text.splitlines():
        found = _candidates(line, fld)
        (steered if any(s in line.lower() for s in STEER) else plain).extend(found)
    if steered:
        return steered[-1]
    return plain[0] if plain else None


# --- a toy text detector, standing in for a prompt-injection classifier ------------------------
DETECTOR_PATTERNS = [re.compile(p, re.I) for p in (
    r"ignore (all |any )?(previous|prior|above)", r"\bsystem\s*:", r"note to (the )?ai",
    r"assistant instructions?", r"disregard",
)]


def detector_flags(text: str) -> bool:
    return any(p.search(text) for p in DETECTOR_PATTERNS)


# --- baseline agents ----------------------------------------------------------------------
class NaiveAgent:
    name = "undefended"

    def run(self, command: str, docs: list[Document], rail: MockUPIRail, billers: dict | None = None) -> RunResult:
        context = command + "\n" + "\n".join(d.text for d in docs)
        upi = gullible_read(context, "upi")
        amount = gullible_read(context, "amount")
        trace = [f"model read {len(docs)} source(s) in one context", f"chose payee={upi}, amount={amount}"]
        if upi is None or amount is None:
            return RunResult(self.name, None, "failed", ["could not find payee or amount"], trace=trace)
        if amount > UPI_CIRCLE_PER_TXN_CAP:
            return RunResult(self.name, None, "blocked", [f"over ₹{UPI_CIRCLE_PER_TXN_CAP} cap"], trace=trace)
        credit = rail.pay(upi, amount, command)
        return RunResult(self.name, credit, "paid", ["within spending cap", "agent authenticated"], trace=trace)


class DetectorGuardedAgent(NaiveAgent):
    name = "detector"

    def run(self, command, docs, rail, billers=None):
        flagged = [d.source for d in docs if detector_flags(d.text)]
        if flagged:
            return RunResult(self.name, None, "blocked", [f"detector flagged {', '.join(flagged)}"],
                             trace=["detector scanned inputs", f"flagged {flagged}"])
        r = super().run(command, docs, rail)
        r.agent = self.name
        r.trace.insert(0, "detector scanned inputs: nothing flagged")
        return r


# --- Mool ---------------------------------------------------------------------------------
USER_AMT_RE = re.compile(r"(?:₹|rs\.?\s*)([0-9][0-9,]*)|([0-9][0-9,]*)\s*(?:rupaye|rupees|rupay|रुपये)", re.I)


class Planner:
    """Privileged. Sees only the user's words and the user's own data. Never sees documents."""

    def plan(self, command: str, doc_sources: list[str]) -> list[dict]:
        contact = find_contact_in(command)
        m = USER_AMT_RE.search(command)
        steps: list[dict] = [{"op": "read", "docs": doc_sources, "out": "bill"}]
        if contact:
            steps.append({"op": "contact_upi", "name": contact.name, "out": "payee"})
        else:
            steps.append({"op": "extract", "from": "bill", "field": "upi", "out": "payee"})
        if m:
            steps.append({"op": "user_amount", "value": int((m.group(1) or m.group(2)).replace(",", "")), "out": "amount"})
        elif contact and contact.biller:
            steps.append({"op": "bill_fetch", "name": contact.name, "out": "amount"})
        else:
            steps.append({"op": "extract", "from": "bill", "field": "amount", "out": "amount"})
        steps.append({"op": "pay", "payee": "payee", "amount": "amount"})
        return steps


class QuarantinedExtractor:
    """Reads untrusted text. Has no tools. Whatever it returns inherits the text's taint."""

    def __init__(self, model=gullible_read):
        self.model = model

    def extract(self, source: Tagged, fld: str) -> Tagged:
        return source.derive(self.model(str(source.value), fld))


class MoolAgent:
    name = "mool"

    def __init__(self, extractor: QuarantinedExtractor | None = None):
        self.planner = Planner()
        self.extractor = extractor or QuarantinedExtractor()
        self.last_receipt_hash: str | None = None

    def run(self, command: str, docs: list[Document], rail: MockUPIRail, billers: dict | None = None) -> RunResult:
        from .world import CONTACTS
        from .receipt import sha256
        plan = self.planner.plan(command, [d.source for d in docs])
        env: dict[str, Tagged] = {}
        trace: list = []
        for step in plan:
            op = step["op"]
            if op == "read":
                env[step["out"]] = Tagged("\n".join(d.text for d in docs),
                                          frozenset().union(*[tag(None, Trust.UNTRUSTED, d.source).origins for d in docs]))
            elif op == "contact_upi":
                c = next(c for c in CONTACTS if c.name == step["name"])
                env[step["out"]] = tag(c.upi, Trust.CONTACTS, f"contacts:{c.name}")
            elif op == "bill_fetch":
                # Bharat Connect bill fetch: the biller's own system states the amount due.
                env[step["out"]] = tag((billers or {}).get(step["name"]), Trust.REGISTRY, f"bharat-connect:{step['name']}")
            elif op == "user_amount":
                env[step["out"]] = tag(step["value"], Trust.USER, "user:command")
            elif op == "extract":
                env[step["out"]] = self.extractor.extract(env[step["from"]], step["field"])
            elif op == "pay":
                payee, amount = env[step["payee"]], env[step["amount"]]
                d: Decision = check_payment(payee, amount)
                trace.append({"step": step, "payee": payee.to_dict(), "amount": amount.to_dict()})
                if d.verdict == Verdict.HOLD:
                    return RunResult(self.name, None, "hold", d.reasons, d.question, trace=trace)
                credit = rail.pay(str(payee.value), int(amount.value), command)
                receipt = sign_receipt(command, plan, payee, amount, credit, prev=self.last_receipt_hash)
                self.last_receipt_hash = sha256(receipt)
                return RunResult(self.name, credit, "paid", d.reasons, receipt=receipt, trace=trace)
            if op != "pay" and op != "read":
                trace.append({"step": step, "value": env[step["out"]].to_dict()})
        raise RuntimeError("plan had no pay step")
