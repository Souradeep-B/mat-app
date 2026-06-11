"""
campaigns.py — The `campaigns` table: your master spreadsheet, migrated to DB.

This is the HUB table. `campaign_uid` (surrogate PK) is the universal join key
that every other table (approvals, audience_files, delivery_metrics, …) points
to. The three business identifiers — opm_ticket, wf_number, campaign_id — are
the human-facing lookup keys (used by Monitoring/ROI "enter a number" flows).

Columns mirror the master spreadsheet 1:1, plus campaign_uid.
"""

import uuid
from sqlalchemy import Table, Column, String, select, insert, update, delete
from db import engine, metadata, now_iso

# Column order follows the master spreadsheet (campaign_uid added as PK).
campaigns = Table(
    "campaigns", metadata,
    Column("campaign_uid",            String, primary_key=True),   # universal join key
    Column("opm_ticket",              String),                     # lookup key
    Column("wf_number",               String),                     # lookup key
    Column("client",                  String),
    Column("campaign_name",           String),
    Column("campaign_type",           String),
    Column("channel",                 String),
    Column("brd_link",                String),
    Column("intake_date",             String),
    Column("notebook_link",           String),
    Column("approval_subject_line",   String),
    Column("approval_sent_at",        String),
    Column("approval_status",         String),
    Column("approval_updated_at",     String),
    Column("approval_recipients",     String),
    Column("campaign_id",             String),                     # lookup key (platform ID)
    Column("launch_date",             String),
    Column("t1_report_sent_at",       String),
    Column("t2_report_sent_at",       String),
    Column("roi_report_generated_at", String),
    Column("row_created_at",          String),
    Column("last_updated_at",         String),
    Column("created_by",              String),                     # → users.email
    # Repull request (set by the approver; picked up by the scheduled flow)
    Column("repull_date",             String),
    Column("repull_requested_by",     String),
    Column("repull_requested_at",     String),
)

# All spreadsheet columns (excludes the surrogate PK + bookkeeping timestamps)
_DATA_COLS = [
    "opm_ticket", "wf_number", "client", "campaign_name", "campaign_type",
    "channel", "brd_link", "intake_date", "notebook_link",
    "approval_subject_line", "approval_sent_at", "approval_status",
    "approval_updated_at", "approval_recipients", "campaign_id", "launch_date",
    "t1_report_sent_at", "t2_report_sent_at", "roi_report_generated_at",
    "created_by", "repull_date", "repull_requested_by", "repull_requested_at",
]


# ── Lookups ───────────────────────────────────────────────────────────────────
def _row_to_dict(row):
    return dict(row) if row else None


def get_campaign_by_uid(uid: str) -> dict | None:
    with engine.connect() as c:
        return _row_to_dict(c.execute(
            select(campaigns).where(campaigns.c.campaign_uid == uid)
        ).mappings().first())


def get_campaign_by_ticket(opm_ticket: str) -> dict | None:
    with engine.connect() as c:
        return _row_to_dict(c.execute(
            select(campaigns).where(campaigns.c.opm_ticket == opm_ticket)
        ).mappings().first())


def get_campaign_by_wf(wf_number: str) -> dict | None:
    with engine.connect() as c:
        return _row_to_dict(c.execute(
            select(campaigns).where(campaigns.c.wf_number == wf_number)
        ).mappings().first())


def get_campaign_by_campaign_id(campaign_id: str) -> dict | None:
    with engine.connect() as c:
        return _row_to_dict(c.execute(
            select(campaigns).where(campaigns.c.campaign_id == campaign_id)
        ).mappings().first())


def find_campaign(query: str) -> dict | None:
    """Flexible lookup for Monitoring/ROI: try OPM ticket → WF number → campaign_id.
    Lets a user type any one of the three identifiers and resolve the campaign."""
    q = (query or "").strip()
    if not q:
        return None
    return (
        get_campaign_by_ticket(q)
        or get_campaign_by_wf(q)
        or get_campaign_by_campaign_id(q)
    )


def list_campaigns() -> list[dict]:
    with engine.connect() as c:
        rows = c.execute(
            select(campaigns).order_by(campaigns.c.row_created_at.desc())
        ).mappings().all()
    return [dict(r) for r in rows]


def list_campaigns_by_user(email: str) -> list[dict]:
    with engine.connect() as c:
        rows = c.execute(
            select(campaigns).where(campaigns.c.created_by == email)
            .order_by(campaigns.c.row_created_at.desc())
        ).mappings().all()
    return [dict(r) for r in rows]


# ── Writes ────────────────────────────────────────────────────────────────────
def upsert_campaign(data: dict) -> str:
    """Insert a new campaign or update an existing one.

    Match key (in priority order): opm_ticket → campaign_id → wf_number.
    Returns the campaign_uid. Only known columns are written; unknown keys are
    ignored. row_created_at is set on insert; last_updated_at on every write.
    """
    clean = {k: v for k, v in data.items() if k in _DATA_COLS}

    existing = None
    if clean.get("opm_ticket"):
        existing = get_campaign_by_ticket(clean["opm_ticket"])
    if not existing and clean.get("campaign_id"):
        existing = get_campaign_by_campaign_id(clean["campaign_id"])
    if not existing and clean.get("wf_number"):
        existing = get_campaign_by_wf(clean["wf_number"])

    with engine.begin() as c:
        if existing:
            uid = existing["campaign_uid"]
            c.execute(
                update(campaigns).where(campaigns.c.campaign_uid == uid)
                .values(**clean, last_updated_at=now_iso())
            )
        else:
            uid = uuid.uuid4().hex
            c.execute(insert(campaigns).values(
                campaign_uid=uid, **clean,
                row_created_at=now_iso(), last_updated_at=now_iso(),
            ))
    return uid


def update_campaign(uid: str, **fields) -> None:
    """Update specific columns on a campaign by its uid."""
    clean = {k: v for k, v in fields.items() if k in _DATA_COLS}
    if not clean:
        return
    with engine.begin() as c:
        c.execute(
            update(campaigns).where(campaigns.c.campaign_uid == uid)
            .values(**clean, last_updated_at=now_iso())
        )


def delete_campaign(uid: str) -> None:
    with engine.begin() as c:
        c.execute(delete(campaigns).where(campaigns.c.campaign_uid == uid))
