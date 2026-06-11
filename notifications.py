"""
notifications.py — In-app notifications (Tier 3, pulled forward for the
dashboard/approval flow).

A notification is created for a user when something happens that concerns
them (approval requested, approved, rejected). The dashboard shows unread
ones; is_read flips when the user clears them.
"""

import uuid
from sqlalchemy import Table, Column, String, Text, select, insert, update
from db import engine, metadata, now_iso

notifications = Table(
    "notifications", metadata,
    Column("notif_uid",    String, primary_key=True),
    Column("user_email",   String),   # recipient → users.email
    Column("campaign_uid", String),   # FK → campaigns.campaign_uid
    Column("opm_ticket",   String),
    Column("message",      Text),
    Column("is_read",      String, default="0"),   # "0" / "1" (portable)
    Column("created_at",   String),
)


def notify(user_email: str, campaign_uid: str, opm_ticket: str, message: str) -> str:
    uid = uuid.uuid4().hex
    with engine.begin() as c:
        c.execute(insert(notifications).values(
            notif_uid=uid, user_email=user_email, campaign_uid=campaign_uid,
            opm_ticket=opm_ticket, message=message, is_read="0",
            created_at=now_iso(),
        ))
    return uid


def get_unread(user_email: str) -> list[dict]:
    with engine.connect() as c:
        rows = c.execute(
            select(notifications)
            .where(notifications.c.user_email == user_email,
                   notifications.c.is_read == "0")
            .order_by(notifications.c.created_at.desc())
        ).mappings().all()
    return [dict(r) for r in rows]


def get_recent(user_email: str, limit: int = 20) -> list[dict]:
    with engine.connect() as c:
        rows = c.execute(
            select(notifications)
            .where(notifications.c.user_email == user_email)
            .order_by(notifications.c.created_at.desc())
            .limit(limit)
        ).mappings().all()
    return [dict(r) for r in rows]


def mark_all_read(user_email: str) -> None:
    with engine.begin() as c:
        c.execute(
            update(notifications)
            .where(notifications.c.user_email == user_email)
            .values(is_read="1")
        )
