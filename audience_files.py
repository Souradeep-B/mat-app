"""
audience_files.py — Generated audience file references (Tier 1).

PII RULE: never stores member rows — only the Google Drive link + row count.
The actual audience CSVs live in Drive; this table just points to them.
Linked to campaigns via campaign_uid.
"""

import uuid
from sqlalchemy import Table, Column, String, Integer, select, insert, delete
from db import engine, metadata, now_iso

audience_files = Table(
    "audience_files", metadata,
    Column("file_uid",     String, primary_key=True),
    Column("campaign_uid", String),     # FK → campaigns.campaign_uid
    Column("opm_ticket",   String),
    Column("file_type",    String),     # EM1 / DM1 / Summary
    Column("drive_link",   String),
    Column("row_count",    Integer),
    Column("generated_by", String),
    Column("generated_at", String),
)


def add_audience_file(campaign_uid: str, opm_ticket: str, file_type: str,
                      drive_link: str, row_count: int, generated_by: str) -> str:
    uid = uuid.uuid4().hex
    with engine.begin() as c:
        c.execute(insert(audience_files).values(
            file_uid=uid, campaign_uid=campaign_uid, opm_ticket=opm_ticket,
            file_type=file_type, drive_link=drive_link,
            row_count=int(row_count or 0), generated_by=generated_by,
            generated_at=now_iso(),
        ))
    return uid


def get_files_for_campaign(campaign_uid: str) -> list[dict]:
    with engine.connect() as c:
        rows = c.execute(
            select(audience_files).where(audience_files.c.campaign_uid == campaign_uid)
            .order_by(audience_files.c.generated_at.desc())
        ).mappings().all()
    return [dict(r) for r in rows]


def delete_file(file_uid: str) -> None:
    with engine.begin() as c:
        c.execute(delete(audience_files).where(audience_files.c.file_uid == file_uid))


def list_audience_files() -> list[dict]:
    with engine.connect() as c:
        rows = c.execute(select(audience_files).order_by(audience_files.c.generated_at.desc())).mappings().all()
    return [dict(r) for r in rows]
