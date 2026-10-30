"""Postgres storage for what the gate must remember across restarts:
owners and their plan level, agents and their keys, held payments, and
every gate decision."""

from functools import lru_cache

import psycopg
from psycopg.rows import dict_row

from config import get_settings

SCHEMA = """
create table if not exists owners (
    email       text primary key,
    level       text not null default 'normal'
                check (level in ('normal', 'pause', 'protection', 'closure')),
    vault_id    text,
    updated_at  timestamptz not null default now()
);

create table if not exists agents (
    id            text primary key,
    owner_email   text not null references owners (email),
    name          text not null,
    category      text not null check (category in ('essential', 'non_essential')),
    status        text not null default 'active'
                  check (status in ('active', 'suspended', 'revoked')),
    spending_cap  numeric(12, 2) not null check (spending_cap > 0),
    key_hash      text not null unique,
    created_at    timestamptz not null default now()
);

create table if not exists holds (
    authorization_id  text primary key,
    owner_email       text not null references owners (email),
    agent_id          text not null references agents (id),
    amount            numeric(12, 2) not null,
    currency          text not null,
    description       text,
    status            text not null default 'held'
                      check (status in ('held', 'captured', 'voided')),
    created_at        timestamptz not null default now(),
    settled_at        timestamptz
);

-- Emergency fund settings, registered while the owner is well (G5, G6).
alter table owners add column if not exists fund_cap numeric(12, 2);
alter table owners add column if not exists fund_email text;

-- Level 3: a confirmed closure request waits 72 hours before it takes effect.
alter table owners add column if not exists closure_requested_at timestamptz;
alter table owners add column if not exists closure_requested_by text;

-- Subscriptions suspended at level 2, so a returning owner gets them back.
create table if not exists suspended_subscriptions (
    subscription_id  text primary key,
    owner_email      text not null references owners (email),
    suspended_at     timestamptz not null default now(),
    reactivated_at   timestamptz
);

create table if not exists gate_events (
    id           bigserial primary key,
    at           timestamptz not null default now(),
    owner_email  text not null,
    agent_id     text,
    action       text not null,
    amount       numeric(12, 2),
    currency     text,
    outcome      text not null,
    reason       text,
    paypal_id    text
);
"""


class DatabaseNotConfigured(Exception):
    pass


@lru_cache
def _ensure_schema(url: str) -> None:
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute(SCHEMA)


def connect() -> psycopg.Connection:
    url = get_settings().database_url
    if not url:
        raise DatabaseNotConfigured()
    _ensure_schema(url)
    return psycopg.connect(url, row_factory=dict_row, autocommit=True)


def log_event(conn, owner_email, action, outcome, *, agent_id=None, amount=None,
              currency=None, reason=None, paypal_id=None) -> None:
    conn.execute(
        """insert into gate_events
               (owner_email, agent_id, action, amount, currency, outcome, reason, paypal_id)
           values (%s, %s, %s, %s, %s, %s, %s, %s)""",
        (owner_email, agent_id, action, amount, currency, outcome, reason, paypal_id),
    )
