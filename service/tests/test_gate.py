from decimal import Decimal

import pytest

from gate import may_capture, refusal, simulate


def check(level="normal", vault=True, status="active", category="non_essential",
          cap="150", amount="42.50", currency="USD"):
    return refusal(level, vault, status, category, Decimal(cap), Decimal(amount), currency)


def test_an_active_agent_within_its_cap_may_pay():
    assert check() is None


@pytest.mark.parametrize("level", ["pause", "protection"])
def test_non_essential_agents_stop_while_the_owner_is_silent(level):
    assert "on hold" in check(level=level, category="non_essential")


@pytest.mark.parametrize("level", ["pause", "protection"])
def test_essential_agents_keep_paying_while_the_owner_is_silent(level):
    assert check(level=level, category="essential") is None


def test_no_agent_pays_once_the_plan_is_closed():
    assert "closed" in check(level="closure", category="essential")


@pytest.mark.parametrize("status, word", [("suspended", "suspended"), ("revoked", "revoked")])
def test_a_suspended_or_revoked_agent_cannot_pay(status, word):
    assert word in check(status=status)


def test_spending_cap_is_enforced():
    assert check(cap="150", amount="150.00") is None
    assert "spending cap" in check(cap="150", amount="150.01")


def test_payment_needs_paypal_connected_and_a_positive_usd_amount():
    assert "connected PayPal" in check(vault=False)
    assert "USD" in check(currency="EUR")
    assert "greater than zero" in check(amount="0")


def test_held_payments_complete_only_when_the_agent_could_still_pay():
    assert may_capture("normal", "non_essential")
    assert not may_capture("pause", "non_essential")
    assert may_capture("pause", "essential")
    assert may_capture("protection", "essential")
    assert not may_capture("closure", "essential")


AGENTS = [
    {"id": "grocery", "name": "Grocery agent", "category": "non_essential", "status": "active"},
    {"id": "bills", "name": "Utility bills agent", "category": "essential", "status": "active"},
    {"id": "old", "name": "Old agent", "category": "non_essential", "status": "suspended"},
]
HOLDS = [
    {"agent_id": "grocery", "amount": "42.50", "currency": "USD", "description": "Groceries"},
    {"agent_id": "bills", "amount": "85.00", "currency": "USD", "description": "Electricity"},
]


def test_rehearsal_of_a_pause_stops_shopping_but_keeps_bills():
    result = simulate("pause", AGENTS, HOLDS)
    assert [a["agent_id"] for a in result["agents_stopped"]] == ["grocery"]
    assert [a["agent_id"] for a in result["agents_continuing"]] == ["bills"]
    assert [h["agent_id"] for h in result["held_payments_cancelled"]] == ["grocery"]
    assert [h["agent_id"] for h in result["held_payments_still_completed"]] == ["bills"]
    assert "Nothing was changed" in result["note"]


def test_rehearsal_of_a_closure_stops_every_agent():
    result = simulate("closure", AGENTS, HOLDS)
    assert {a["agent_id"] for a in result["agents_stopped"]} == {"grocery", "bills"}
    assert result["held_payments_still_completed"] == []


def test_rehearsal_rejects_an_unknown_level():
    with pytest.raises(ValueError):
        simulate("panic", AGENTS, HOLDS)
