"""
approvals.py — Approval workflow history (Tier 1).

Full audit trail of approval requests and decisions. campaigns.approval_status
holds the latest snapshot; this table holds every request/decision with who+when.
Linked to campaigns via campaign_uid.
"""

import uuid
from sqlalchemy import Table, Column, String, Text, select, insert, update
from db import engine, metadata, now_iso

approvals = Table(
    "approvals", metadata,
    Column("approval_uid", String, primary_key=True),
    Column("campaign_uid", String),          # FK → campaigns.campaign_uid
    Column("opm_ticket",   String),          # denormalised for easy lookup
    Column("requested_by", String),          # → users.email
    Column("assigned_to",  String),          # approver → users.email
    Column("status",       String),          # Pending / Approved / Rejected / Repull Requested
    Column("requested_at", String),
    Column("acted_at",     String),
    Column("notes",        Text),
    Column("report_ref",   String),          # optional link to the approval report
    Column("report_html",  Text),            # full audience summary report (HTML)
)


def create_approval(campaign_uid: str, opm_ticket: str, requested_by: str,
                    assigned_to: str, report_ref: str = "", report_html: str = "") -> str:
    uid = uuid.uuid4().hex
    with engine.begin() as c:
        c.execute(insert(approvals).values(
            approval_uid=uid, campaign_uid=campaign_uid, opm_ticket=opm_ticket,
            requested_by=requested_by, assigned_to=assigned_to, status="Pending",
            requested_at=now_iso(), acted_at="", notes="", report_ref=report_ref,
            report_html=report_html or "",
        ))
    return uid


def set_status(approval_uid: str, status: str, notes: str = "") -> None:
    with engine.begin() as c:
        c.execute(update(approvals).where(approvals.c.approval_uid == approval_uid)
                  .values(status=status, acted_at=now_iso(), notes=notes))


def get_approval(approval_uid: str) -> dict | None:
    with engine.connect() as c:
        row = c.execute(select(approvals).where(approvals.c.approval_uid == approval_uid)).mappings().first()
    return dict(row) if row else None


def get_pending_for(assignee_email: str) -> list[dict]:
    """Pending approvals assigned to a given approver (their dashboard inbox)."""
    with engine.connect() as c:
        rows = c.execute(
            select(approvals).where(approvals.c.assigned_to == assignee_email,
                                    approvals.c.status == "Pending")
            .order_by(approvals.c.requested_at)
        ).mappings().all()
    return [dict(r) for r in rows]


def get_by_campaign(campaign_uid: str) -> list[dict]:
    with engine.connect() as c:
        rows = c.execute(
            select(approvals).where(approvals.c.campaign_uid == campaign_uid)
            .order_by(approvals.c.requested_at.desc())
        ).mappings().all()
    return [dict(r) for r in rows]


def list_approvals() -> list[dict]:
    with engine.connect() as c:
        rows = c.execute(select(approvals).order_by(approvals.c.requested_at.desc())).mappings().all()
    return [dict(r) for r in rows]
