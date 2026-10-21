"""The gate's rules: whether an agent may pay, and whether a held payment
may be completed. Pure functions, so every rule can be tested without
PayPal or a database (guardrails G3, G4, G12)."""

from decimal import Decimal

LEVELS = ("normal", "pause", "protection", "closure")
# Levels where only essential agents keep paying (plan levels 1 and 2).
ESSENTIAL_ONLY_LEVELS = {"pause", "protection"}
CURRENCY = "USD"


def refusal(
    owner_level: str,
    has_vault: bool,
    agent_status: str,
    agent_category: str,
    spending_cap: Decimal,
    amount: Decimal,
    currency: str,
) -> str | None:
    """None if the agent may pay, otherwise the reason it can't, worded for the agent."""
    if agent_status == "suspended":
        return "This agent is suspended by the owner."
    if agent_status == "revoked":
        return "This agent's permission to pay has been revoked."
    if owner_level == "closure":
        return "The owner's plan is closed. No agent can pay."
    if owner_level in ESSENTIAL_ONLY_LEVELS and agent_category != "essential":
        return "The owner isn't responding, so payments by non-essential agents are on hold."
    if not has_vault:
        return "The owner hasn't connected PayPal yet."
    if currency != CURRENCY:
        return f"Only {CURRENCY} payments are supported."
    if amount <= 0:
        return "The amount must be greater than zero."
    if amount > spending_cap:
        return f"The amount is above this agent's spending cap of {spending_cap} {CURRENCY}."
    return None


def simulate(level: str, agents: list[dict], holds: list[dict]) -> dict:
    """What a plan level would do right now, without doing it (the rehearsal, Z3).

    `agents` need id, name, category, status; `holds` need agent_id, amount,
    currency, description.
    """
    if level not in LEVELS:
        raise ValueError(f"Unknown level: {level}")
    by_id = {agent["id"]: agent for agent in agents}
    stopped, continuing = [], []
    for agent in agents:
        if agent["status"] != "active":
            continue
        reason = refusal(level, True, "active", agent["category"], Decimal("1"), Decimal("1"), CURRENCY)
        entry = {"agent_id": agent["id"], "name": agent["name"], "category": agent["category"]}
        if reason:
            stopped.append({**entry, "reason": reason})
        else:
            continuing.append(entry)
    cancelled, completed = [], []
    for hold in holds:
        agent = by_id.get(hold["agent_id"])
        if agent is None:
            continue
        item = {"agent_id": hold["agent_id"], "amount": str(hold["amount"]),
                "currency": hold["currency"], "description": hold.get("description")}
        if agent["status"] == "active" and may_capture(level, agent["category"]):
            completed.append(item)
        else:
            cancelled.append(item)
    return {
        "level": level,
        "agents_stopped": stopped,
        "agents_continuing": continuing,
        "held_payments_cancelled": cancelled,
        "held_payments_still_completed": completed,
        "note": "Rehearsal only. Nothing was changed.",
    }


def may_capture(owner_level: str, agent_category: str) -> bool:
    """A held payment is completed only if the agent could still start it now."""
    if owner_level == "closure":
        return False
    if owner_level in ESSENTIAL_ONLY_LEVELS:
        return agent_category == "essential"
    return True
