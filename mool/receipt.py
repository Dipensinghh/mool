"""Signed intent receipts: per-payment evidence linking money to the words a human spoke."""
from __future__ import annotations
import hashlib, hmac, json, os
from datetime import datetime, timezone

DEMO_KEY = os.environ.get("MOOL_RECEIPT_KEY", "mool-demo-key-do-not-use-in-production").encode()


def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()


def sha256(data) -> str:
    return hashlib.sha256(data if isinstance(data, bytes) else canonical(data)).hexdigest()


def sign_receipt(command: str, plan: list, payee, amount, credit, prev: str | None = None,
                 key: bytes = DEMO_KEY, ts: str | None = None) -> dict:
    body = {
        "version": "mool-receipt/0.1",
        "command": command,
        "command_sha256": sha256(command.encode()),
        "plan_sha256": sha256(plan),
        "payee": payee.to_dict(),
        "amount": amount.to_dict(),
        "payment": {"txn_id": credit.txn_id, "upi": credit.upi, "amount": credit.amount},
        "issued_at": ts or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "prev": prev,
    }
    return {"body": body, "signature": hmac.new(key, canonical(body), hashlib.sha256).hexdigest()}


def verify_receipt(receipt: dict, key: bytes = DEMO_KEY) -> bool:
    expected = hmac.new(key, canonical(receipt["body"]), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, receipt["signature"])
