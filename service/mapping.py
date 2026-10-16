"""Turns raw PayPal transactions into the payment map the AI classifies.

Three jobs, all done with fixed rules rather than the AI:
- drop PayPal's internal bookkeeping (holds and their releases);
- group repeated payments and mark the recurring ones;
- replace every person's details with a stable code (controls P1 and P3).
"""

import hashlib
import hmac
from decimal import Decimal

# Event codes are PayPal's transaction types. These families are not payments
# the owner makes, so they stay out of the map:
#   T01xx fees, T03xx money added from a bank, T04xx money moved to a bank,
#   T11xx reversals and releases, T15xx holds (both mirror a real payment),
#   T19xx account adjustments (e.g. the sandbox's initial balance).
NOISE_PREFIXES = ("T01", "T03", "T04", "T11", "T15", "T19")
KIND_BY_CODE = {
    "T0001": "payout",  # money we sent, e.g. rent paid on the owner's behalf
    "T0002": "subscription",  # a charge on a PayPal subscription
}
# S = completed, P = pending. Denied or reversed payments are not part of the map.
KEPT_STATUSES = {"S", "P"}
TEXT_LIMIT = 140


def pseudonym(value: str, key: str, prefix: str) -> str:
    digest = hmac.new(key.encode(), value.encode(), hashlib.sha256).hexdigest()
    return f"{prefix}-{digest[:8]}"


def _short(text: str | None) -> str | None:
    return text[:TEXT_LIMIT] if text else None


def build_map(transactions: list[dict], key: str) -> dict:
    groups: dict[tuple, dict] = {}
    ignored = 0

    for transaction in transactions:
        info = transaction.get("transaction_info", {})
        code = info.get("transaction_event_code", "")
        if code.startswith(NOISE_PREFIXES) or info.get("transaction_status") not in KEPT_STATUSES:
            ignored += 1
            continue

        payer = transaction.get("payer_info", {})
        person = payer.get("account_id") or payer.get("email_address")
        counterparty = pseudonym(person, key, "P") if person else None

        kind = KIND_BY_CODE.get(code, "payment")
        subject = _short(info.get("transaction_subject"))
        subscription_id = (
            info.get("paypal_reference_id") if info.get("paypal_reference_id_type") == "RP" else None
        )
        group_key = ("subscription", subscription_id) if subscription_id else (kind, counterparty, subject)

        amount = abs(Decimal(info["transaction_amount"]["value"]))
        date = info.get("transaction_initiation_date", "")
        group = groups.get(group_key)
        if group is None:
            group = groups[group_key] = {
                "item_id": pseudonym(repr(group_key), key, "M"),
                "kind": "subscription" if subscription_id else kind,
                "description": subject,
                "note": _short(info.get("transaction_note")),
                "counterparty": counterparty,
                "currency": info["transaction_amount"]["currency_code"],
                "subscription_id": subscription_id,
                "occurrences": 0,
                "total": Decimal("0"),
                "first_seen": date,
                "last_seen": date,
                "last_amount": amount,
            }
        group["occurrences"] += 1
        group["total"] += amount
        group["first_seen"] = min(group["first_seen"], date)
        if date >= group["last_seen"]:
            group["last_seen"] = date
            group["last_amount"] = amount

    payments = []
    for group in sorted(groups.values(), key=lambda g: g["last_seen"], reverse=True):
        group["recurring"] = bool(group["subscription_id"]) or group["occurrences"] >= 2
        group["total"] = str(group["total"])
        group["last_amount"] = str(group["last_amount"])
        payments.append(group)

    return {"payments": payments, "ignored_bookkeeping": ignored}
