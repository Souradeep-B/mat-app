"""
db.py — Shared database layer for MAT.

One engine + one MetaData for ALL tables (users, campaigns, approvals, …).
Backend auto-selected:
  • DATABASE_URL set   → PostgreSQL (Supabase) — Streamlit Cloud
  • DATABASE_URL unset → SQLite (marketing_automation.db) — local

Every table module (auth.py, campaigns.py, …) imports `engine` and `metadata`
from here and defines its Table on the shared `metadata`. Call `init_db()` once
at startup to create any missing tables.
"""

import os
import datetime
from sqlalchemy import create_engine, MetaData


def _make_engine():
    url = os.environ.get("DATABASE_URL", "").strip()
    if url:
        # SQLAlchemy needs 'postgresql://' (Supabase sometimes gives 'postgres://')
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        return create_engine(url, pool_pre_ping=True)
    db_path = os.path.join(os.path.dirname(__file__), "marketing_automation.db")
    return create_engine(f"sqlite:///{db_path}")


engine   = _make_engine()
metadata = MetaData()


def now_iso() -> str:
    """UTC timestamp as an ISO string — portable across SQLite and Postgres."""
    return datetime.datetime.utcnow().isoformat(timespec="seconds")


def init_db():
    """Create all tables that don't exist yet.
    Imports the table-defining modules so their Tables register on `metadata`."""
    import auth            # noqa: F401  users
    import campaigns       # noqa: F401  campaigns (hub — campaign_uid join key)
    import client_config   # noqa: F401  per-client Sanity config cache
    import approvals       # noqa: F401  approval workflow history
    import audience_files  # noqa: F401  audience file refs (Drive links + counts, no PII)
    import notifications   # noqa: F401  in-app notifications (dashboard)
    metadata.create_all(engine)
    _migrate()


def _migrate():
    """Additive column migrations for tables that already exist.
    create_all() only creates missing TABLES — it never adds columns.
    Each statement is idempotent via try/except (column already exists)."""
    from sqlalchemy import text
    stmts = [
        "ALTER TABLE approvals ADD COLUMN report_html TEXT",
        "ALTER TABLE campaigns ADD COLUMN repull_date TEXT",
        "ALTER TABLE campaigns ADD COLUMN repull_requested_by TEXT",
        "ALTER TABLE campaigns ADD COLUMN repull_requested_at TEXT",
    ]
    for s in stmts:
        try:
            with engine.begin() as c:
                c.execute(text(s))
        except Exception:
            pass  # column already exists
