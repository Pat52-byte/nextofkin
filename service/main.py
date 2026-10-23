"""NextOfKin service: the only part of the system that talks to PayPal.

Zapier orchestrates the flows; this service makes the PayPal calls and
enforces the fixed safety rules the AI cannot override.
"""

import hashlib
import hmac
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from functools import lru_cache

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import db
from config import get_settings
from gate import CURRENCY, LEVELS, may_capture, refusal, simulate
from mapping import build_map
from paypal import PayPalClient, PayPalError

app = FastAPI(title="NextOfKin service", version="0.4.4")

AGENT_ID = re.compile(r"^[a-z0-9-]{2,40}$")


@lru_cache
def paypal() -> PayPalClient:
    return PayPalClient(get_settings())


def require_api_key(x_api_key: str = Header(default="")) -> None:
    """Every Zapier-facing call must carry the shared key Zapier holds (control S6).

    With no key configured the service refuses everything rather than run open.
    """
    expected = get_settings().service_api_key
    if not expected or not hmac.compare_digest(x_api_key, expected):
        raise HTTPException(status_code=401, detail="Missing or wrong X-Api-Key header.")


def key_hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


@app.exception_handler(PayPalError)
def paypal_error(_, error: PayPalError):
    return JSONResponse(
        status_code=502,
        content={
            "error": "paypal_error",
            "paypal_status": error.status,
            "paypal_name": error.name,
            "message": error.message,
            "debug_id": error.debug_id,
        },
    )


@app.exception_handler(db.DatabaseNotConfigured)
def database_missing(_, __):
    return JSONResponse(status_code=503, content={"error": "DATABASE_URL is not configured."})


@app.get("/health")
def health() -> dict:
    """Liveness check used by Render and by Zapier before each flow."""
    return {"status": "ok", "service": "nextofkin", "version": app.version}


@app.get("/map", dependencies=[Depends(require_api_key)])
def payment_map(days: int = Query(30, ge=1, le=31)) -> dict:
    """The owner's payments over the last `days` days, grouped, with people
    replaced by codes. PayPal can take a few hours to list new transactions."""
    settings = get_settings()
    if not settings.pseudonym_key:
        raise HTTPException(status_code=503, detail="PSEUDONYM_KEY is not configured.")
    end = datetime.now(timezone.utc).replace(microsecond=0)
    start = end - timedelta(days=days)
    stamp = "%Y-%m-%dT%H:%M:%SZ"
    transactions = paypal().search_transactions(start.strftime(stamp), end.strftime(stamp))
    return {
        "period": {"start": start.strftime(stamp), "end": end.strftime(stamp)},
        **build_map(transactions, settings.pseudonym_key),
    }


# Owners -------------------------------------------------------------------


class OwnerIn(BaseModel):
    email: str
    vault_id: str | None = None


def load_owner(conn, email: str) -> dict:
    owner = conn.execute("select * from owners where email = %s", (email,)).fetchone()
    if owner is None:
        raise HTTPException(status_code=404, detail="Owner not found.")
    return owner


def void_holds(conn, owner_email: str, *, agent_id: str | None = None,
               non_essential_only: bool = False, reason: str) -> list[str]:
    """Cancel held payments that have not been completed yet (plan level 1)."""
    query = """select h.authorization_id, h.agent_id, h.amount, h.currency
               from holds h join agents a on a.id = h.agent_id
               where h.owner_email = %s and h.status = 'held'"""
    params: list = [owner_email]
    if agent_id:
        query += " and h.agent_id = %s"
        params.append(agent_id)
    if non_essential_only:
        query += " and a.category = 'non_essential'"
    voided = []
    for hold in conn.execute(query, params).fetchall():
        paypal().request(
            "POST",
            f"/v2/payments/authorizations/{hold['authorization_id']}/void",
            headers={"Prefer": "return=representation"},
        )
        conn.execute(
            "update holds set status = 'voided', settled_at = now() where authorization_id = %s",
            (hold["authorization_id"],),
        )
        db.log_event(conn, owner_email, "void", "done", agent_id=hold["agent_id"],
                     amount=hold["amount"], currency=hold["currency"], reason=reason,
                     paypal_id=hold["authorization_id"])
        voided.append(hold["authorization_id"])
    return voided


@app.post("/owners", dependencies=[Depends(require_api_key)])
def upsert_owner(body: OwnerIn) -> dict:
    with db.connect() as conn:
        conn.execute(
            """insert into owners (email, vault_id) values (%s, %s)
               on conflict (email) do update
               set vault_id = coalesce(excluded.vault_id, owners.vault_id), updated_at = now()""",
            (body.email, body.vault_id),
        )
        owner = load_owner(conn, body.email)
    return {"email": owner["email"], "level": owner["level"], "has_vault": bool(owner["vault_id"])}


@app.get("/owners/{email}", dependencies=[Depends(require_api_key)])
def get_owner(email: str) -> dict:
    with db.connect() as conn:
        owner = load_owner(conn, email)
        agents = conn.execute(
            """select id, name, category, status, spending_cap from agents
               where owner_email = %s order by created_at""",
            (email,),
        ).fetchall()
    return {"email": owner["email"], "level": owner["level"],
            "has_vault": bool(owner["vault_id"]), "agents": agents}


@app.post("/owners/{email}/pause", dependencies=[Depends(require_api_key)])
def pause_owner(email: str) -> dict:
    """Plan level 1: non-essential agents stop and their held payments are cancelled.
    Nothing is cancelled for good and essential agents keep paying (G3, G4)."""
    with db.connect() as conn:
        owner = load_owner(conn, email)
        if owner["level"] == "closure":
            raise HTTPException(status_code=409, detail="The plan is closed.")
        if owner["level"] == "normal":
            conn.execute("update owners set level = 'pause', updated_at = now() where email = %s", (email,))
        voided = void_holds(conn, email, non_essential_only=True,
                            reason="Plan paused: the owner did not answer the check-in.")
        db.log_event(conn, email, "pause", "done", reason="Level 1")
    return {"email": email, "level": "pause" if owner["level"] == "normal" else owner["level"],
            "voided_authorizations": voided}


@app.post("/owners/{email}/resume", dependencies=[Depends(require_api_key)])
def resume_owner(email: str) -> dict:
    """The owner is back: the plan returns to normal (G7, the owner always wins)."""
    with db.connect() as conn:
        owner = load_owner(conn, email)
        if owner["level"] == "closure":
            raise HTTPException(status_code=409, detail="The plan is closed and cannot be resumed.")
        conn.execute("update owners set level = 'normal', updated_at = now() where email = %s", (email,))
        db.log_event(conn, email, "resume", "done", reason="The owner answered.")
    return {"email": email, "level": "normal"}


@app.get("/owners/{email}/rehearsal", dependencies=[Depends(require_api_key)])
def rehearsal(email: str, level: str = Query("pause")) -> dict:
    """Show what a level would do to this owner's agents and held payments,
    without changing anything (the rehearsal at the end of onboarding)."""
    if level not in LEVELS or level == "normal":
        raise HTTPException(status_code=422, detail="level must be pause, protection or closure.")
    with db.connect() as conn:
        load_owner(conn, email)
        agents = conn.execute(
            "select id, name, category, status from agents where owner_email = %s order by created_at",
            (email,),
        ).fetchall()
        holds = conn.execute(
            """select agent_id, amount, currency, description from holds
               where owner_email = %s and status = 'held'""",
            (email,),
        ).fetchall()
        db.log_event(conn, email, "rehearsal", "done", reason=f"Rehearsal of level {level}")
    return simulate(level, agents, holds)


@app.get("/owners/{email}/events", dependencies=[Depends(require_api_key)])
def owner_events(email: str, limit: int = Query(50, ge=1, le=500),
                 since_minutes: int | None = Query(None, ge=1, le=44640)) -> dict:
    """Gate decisions, newest first. Each has a stable `id`, so a sync can skip
    the ones it has already copied; `since_minutes` limits it to recent ones."""
    query = """select id, at, agent_id, action, amount, currency, outcome, reason, paypal_id
               from gate_events where owner_email = %s"""
    params: list = [email]
    if since_minutes:
        query += " and at >= now() - make_interval(mins => %s)"
        params.append(since_minutes)
    query += " order by at desc limit %s"
    params.append(limit)
    with db.connect() as conn:
        load_owner(conn, email)
        events = conn.execute(query, params).fetchall()
    return {"email": email, "events": events}


# Agents -------------------------------------------------------------------


class AgentIn(BaseModel):
    owner_email: str
    agent_id: str
    name: str
    category: str = Field(pattern="^(essential|non_essential)$")
    spending_cap: Decimal = Field(gt=0)


@app.post("/agents", dependencies=[Depends(require_api_key)])
def create_agent(body: AgentIn) -> dict:
    """Register an agent. Its key is returned once: the agent uses it to call
    the gate and never sees the owner's PayPal permission (G12)."""
    if not AGENT_ID.match(body.agent_id):
        raise HTTPException(status_code=422, detail="agent_id: 2-40 lowercase letters, digits or dashes.")
    agent_key = secrets.token_urlsafe(32)
    with db.connect() as conn:
        load_owner(conn, body.owner_email)
        if conn.execute("select 1 from agents where id = %s", (body.agent_id,)).fetchone():
            raise HTTPException(status_code=409, detail="An agent with this id already exists.")
        conn.execute(
            """insert into agents (id, owner_email, name, category, spending_cap, key_hash)
               values (%s, %s, %s, %s, %s, %s)""",
            (body.agent_id, body.owner_email, body.name, body.category, body.spending_cap,
             key_hash(agent_key)),
        )
        db.log_event(conn, body.owner_email, "agent_created", "done", agent_id=body.agent_id)
    return {"agent_id": body.agent_id, "agent_key": agent_key,
            "note": "Store this key now. It is not shown again."}


def change_agent(agent_id: str, status: str, reason: str) -> dict:
    with db.connect() as conn:
        agent = conn.execute("select * from agents where id = %s", (agent_id,)).fetchone()
        if agent is None:
            raise HTTPException(status_code=404, detail="Agent not found.")
        if agent["status"] == "revoked":
            raise HTTPException(status_code=409, detail="This agent was revoked and cannot be changed.")
        conn.execute("update agents set status = %s where id = %s", (status, agent_id))
        voided = []
        if status != "active":
            voided = void_holds(conn, agent["owner_email"], agent_id=agent_id, reason=reason)
        db.log_event(conn, agent["owner_email"], f"agent_{status}", "done", agent_id=agent_id, reason=reason)
    return {"agent_id": agent_id, "status": status, "voided_authorizations": voided}


@app.post("/agents/{agent_id}/suspend", dependencies=[Depends(require_api_key)])
def suspend_agent(agent_id: str) -> dict:
    return change_agent(agent_id, "suspended", "Agent suspended by the owner.")


@app.post("/agents/{agent_id}/activate", dependencies=[Depends(require_api_key)])
def activate_agent(agent_id: str) -> dict:
    return change_agent(agent_id, "active", "Agent reactivated by the owner.")


@app.post("/agents/{agent_id}/revoke", dependencies=[Depends(require_api_key)])
def revoke_agent(agent_id: str) -> dict:
    return change_agent(agent_id, "revoked", "Agent's permission to pay revoked.")


# The gate -----------------------------------------------------------------


class PaymentIn(BaseModel):
    amount: Decimal
    currency: str = CURRENCY
    description: str = Field(default="", max_length=127)


@app.post("/gate/pay")
def gate_pay(body: PaymentIn, x_agent_key: str = Header(default="")) -> JSONResponse:
    """Agents call this to pay. The money is held on PayPal, not taken, so it can
    still be cancelled if the owner stops answering (G1, G12)."""
    with db.connect() as conn:
        agent = conn.execute(
            "select * from agents where key_hash = %s", (key_hash(x_agent_key),)
        ).fetchone() if x_agent_key else None
        if agent is None:
            raise HTTPException(status_code=401, detail="Missing or unknown X-Agent-Key header.")
        owner = load_owner(conn, agent["owner_email"])
        reason = refusal(owner["level"], bool(owner["vault_id"]), agent["status"], agent["category"],
                         agent["spending_cap"], body.amount, body.currency)
        if reason:
            db.log_event(conn, owner["email"], "pay", "refused", agent_id=agent["id"],
                         amount=body.amount, currency=body.currency, reason=reason)
            # 200, not 403: a refusal is a normal answer the agent must read and pass
            # on, and no-code tools stop the whole flow on a 4xx (control U12).
            return JSONResponse(status_code=200, content=gate_answer(
                "refused", "Payment refused by the NextOfKin gate. Nothing was charged.", reason=reason))

        order = paypal().request(
            "POST",
            "/v2/checkout/orders",
            headers={"PayPal-Request-Id": str(uuid.uuid4())},
            json={
                "intent": "AUTHORIZE",
                "purchase_units": [{
                    "description": body.description or agent["name"],
                    "amount": {"currency_code": body.currency, "value": f"{body.amount:.2f}"},
                }],
                "payment_source": {"paypal": {"vault_id": owner["vault_id"]}},
            },
        )
        authorizations = (order.get("purchase_units") or [{}])[0].get("payments", {}).get("authorizations", [])
        if not authorizations:
            db.log_event(conn, owner["email"], "pay", "error", agent_id=agent["id"], amount=body.amount,
                         currency=body.currency, reason=f"PayPal order status {order.get('status')}",
                         paypal_id=order.get("id"))
            return JSONResponse(status_code=502, content=gate_answer(
                "error", "The payment could not be held.", reason="PayPal did not hold the payment."))
        authorization_id = authorizations[0]["id"]
        conn.execute(
            """insert into holds (authorization_id, owner_email, agent_id, amount, currency, description)
               values (%s, %s, %s, %s, %s, %s)""",
            (authorization_id, owner["email"], agent["id"], body.amount, body.currency, body.description),
        )
        db.log_event(conn, owner["email"], "pay", "held", agent_id=agent["id"], amount=body.amount,
                     currency=body.currency, paypal_id=authorization_id)
    message = ("Payment held. It will be completed unless the owner's plan is paused first."
               if owner["level"] == "normal" else
               "Payment held. Essential payments keep going while the owner's plan is paused.")
    return JSONResponse(status_code=201, content=gate_answer("held", message,
                                                             authorization_id=authorization_id))


def gate_answer(outcome: str, message: str, reason: str = "", authorization_id: str = "") -> dict:
    """Every gate answer has the same four fields, so a no-code flow can map
    all of them whatever the outcome."""
    return {"outcome": outcome, "message": message, "reason": reason,
            "authorization_id": authorization_id}


@app.post("/gate/settle", dependencies=[Depends(require_api_key)])
def gate_settle(min_age_minutes: int = Query(0, ge=0)) -> dict:
    """Complete the held payments that may still go through. Run on a schedule."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=min_age_minutes)
    captured, skipped = [], []
    with db.connect() as conn:
        holds = conn.execute(
            """select h.*, a.category, o.level from holds h
               join agents a on a.id = h.agent_id join owners o on o.email = h.owner_email
               where h.status = 'held' and h.created_at <= %s""",
            (cutoff,),
        ).fetchall()
        for hold in holds:
            if not may_capture(hold["level"], hold["category"]):
                skipped.append(hold["authorization_id"])
                continue
            paypal().request(
                "POST",
                f"/v2/payments/authorizations/{hold['authorization_id']}/capture",
                headers={"PayPal-Request-Id": f"capture-{hold['authorization_id']}",
                         "Prefer": "return=representation"},
                json={},
            )
            conn.execute(
                "update holds set status = 'captured', settled_at = now() where authorization_id = %s",
                (hold["authorization_id"],),
            )
            db.log_event(conn, hold["owner_email"], "capture", "done", agent_id=hold["agent_id"],
                         amount=hold["amount"], currency=hold["currency"],
                         paypal_id=hold["authorization_id"])
            captured.append(hold["authorization_id"])
    return {"captured": captured, "kept_on_hold": skipped}
