from datetime import datetime, timezone
from decimal import Decimal

from pages import activity_page


def event(**overrides):
    base = {"at": datetime(2026, 11, 4, 11, 39, tzinfo=timezone.utc), "agent_id": "utility-bills-agent",
            "action": "pay", "amount": Decimal("520.00"), "currency": "USD", "outcome": "refused",
            "reason": "The amount is above this agent's spending cap of 400.00 USD.", "paypal_id": None}
    return {**base, **overrides}


def test_a_refusal_shows_its_amount_and_reason():
    page = activity_page("normal", [event()])
    assert "520.00 USD" in page
    assert "spending cap of 400.00 USD" in page
    assert "Agent asked to pay" in page


def test_values_from_the_database_are_escaped():
    page = activity_page("normal", [event(reason="<script>alert(1)</script>")])
    assert "<script>" not in page
    assert "&lt;script&gt;" in page


def test_an_empty_log_says_so():
    assert "No decisions yet." in activity_page("normal", [])
