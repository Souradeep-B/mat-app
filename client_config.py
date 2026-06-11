"""
client_config.py — Per-client Sanity config cache (Tier 1).

Caches the client/affiliation config pulled from Sanity (childOrgId, clientId,
reward cap, affiliations) so Audience Builder §2 can resolve it instantly and
work offline. Keyed by client name.
"""

from sqlalchemy import Table, Column, String, select, insert, update
from db import engine, metadata, now_iso

client_config = Table(
    "client_config", metadata,
    Column("client",                String, primary_key=True),
    Column("child_org_id",          String),
    Column("client_id",             String),
    Column("reward_max_cap",        String),
    Column("reward_earning_end_date", String),
    Column("total_affiliations",    String),
    Column("included_affiliations", String),
    Column("excluded_affiliations", String),
    Column("filter_decision",       String),
    Column("last_synced",           String),
)

_COLS = [
    "child_org_id", "client_id", "reward_max_cap", "reward_earning_end_date",
    "total_affiliations", "included_affiliations", "excluded_affiliations",
    "filter_decision",
]


def get_client_config(client: str) -> dict | None:
    with engine.connect() as c:
        row = c.execute(
            select(client_config).where(client_config.c.client == client)
        ).mappings().first()
    return dict(row) if row else None


def list_client_configs() -> list[dict]:
    with engine.connect() as c:
        rows = c.execute(select(client_config).order_by(client_config.c.client)).mappings().all()
    return [dict(r) for r in rows]


def upsert_client_config(client: str, data: dict) -> None:
    clean = {k: v for k, v in data.items() if k in _COLS}
    with engine.begin() as c:
        exists = c.execute(
            select(client_config.c.client).where(client_config.c.client == client)
        ).first()
        if exists:
            c.execute(update(client_config).where(client_config.c.client == client)
                      .values(**clean, last_synced=now_iso()))
        else:
            c.execute(insert(client_config).values(
                client=client, **clean, last_synced=now_iso()))
