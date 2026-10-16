from mapping import build_map, pseudonym

KEY = "test-key"


def transaction(code, value, date, status="S", payer=None, **info):
    return {
        "transaction_info": {
            "transaction_event_code": code,
            "transaction_amount": {"currency_code": "USD", "value": value},
            "transaction_initiation_date": date,
            "transaction_status": status,
            **info,
        },
        "payer_info": payer or {},
    }


OWNER = {"account_id": "OWNER123", "email_address": "owner@example.com", "phone_number": {"national_number": "5550100"}}
LANDLORD = {"account_id": "LANDLORD9", "email_address": "landlord@example.com"}


def test_drops_holds_and_their_releases():
    result = build_map(
        [
            transaction("T1503", "-500.25", "2026-10-01T09:00:00Z"),
            transaction("T0001", "-500.00", "2026-10-01T09:00:05Z", payer=LANDLORD, transaction_subject="Rent"),
            transaction("T1105", "500.25", "2026-10-01T09:00:05Z"),
        ],
        KEY,
    )
    assert result["ignored_bookkeeping"] == 2
    assert [p["kind"] for p in result["payments"]] == ["payout"]


def test_drops_account_adjustments_such_as_an_initial_balance():
    result = build_map([transaction("T1900", "5000.00", "2026-10-01T04:00:00Z", transaction_subject="Initial balance")], KEY)
    assert result["payments"] == []
    assert result["ignored_bookkeeping"] == 1


def test_subscription_charges_group_into_one_recurring_item():
    charges = [
        transaction("T0002", "12.99", f"2026-{month}-14T10:00:00Z", payer=OWNER,
                    paypal_reference_id="I-SUB1", paypal_reference_id_type="RP",
                    transaction_subject="Streaming monthly")
        for month in ("08", "09", "10")
    ]
    [item] = build_map(charges, KEY)["payments"]
    assert item["kind"] == "subscription"
    assert item["subscription_id"] == "I-SUB1"
    assert item["recurring"] is True
    assert item["occurrences"] == 3
    assert item["total"] == "38.97"
    assert item["last_seen"] == "2026-10-14T10:00:00Z"


def test_single_payout_is_not_recurring_until_it_repeats():
    once = build_map([transaction("T0001", "-500.00", "2026-10-01T09:00:00Z", payer=LANDLORD, transaction_subject="Rent")], KEY)
    assert once["payments"][0]["recurring"] is False

    twice = build_map(
        [
            transaction("T0001", "-500.00", "2026-09-01T09:00:00Z", payer=LANDLORD, transaction_subject="Rent"),
            transaction("T0001", "-500.00", "2026-10-01T09:00:00Z", payer=LANDLORD, transaction_subject="Rent"),
        ],
        KEY,
    )
    assert twice["payments"][0]["recurring"] is True
    assert twice["payments"][0]["last_amount"] == "500.00"


def test_no_personal_details_leave_the_service():
    result = build_map(
        [transaction("T0002", "12.99", "2026-10-14T10:00:00Z", payer=OWNER,
                     paypal_reference_id="I-SUB1", paypal_reference_id_type="RP")],
        KEY,
    )
    text = repr(result)
    for detail in ("OWNER123", "owner@example.com", "5550100"):
        assert detail not in text
    assert result["payments"][0]["counterparty"] == pseudonym("OWNER123", KEY, "P")


def test_denied_payments_are_left_out():
    result = build_map([transaction("T0006", "20.00", "2026-10-02T09:00:00Z", status="D")], KEY)
    assert result["payments"] == []
    assert result["ignored_bookkeeping"] == 1
