"""
auth.py — User management + DB backend for MAT authentication.

Database (auto-selected):
  • DATABASE_URL set   → PostgreSQL (Supabase) — used on Streamlit Cloud
  • DATABASE_URL unset → SQLite file (marketing_automation.db) — used locally

Same code, both backends, via SQLAlchemy.

Tables:
  users — email (PK), name, picture_url, role, created_at

Roles (most → least permission):
  Admin · Campaign Manager · Approver · Viewer (default on first login)
"""

import os
import hmac
import hashlib

from sqlalchemy import Table, Column, String, select, insert, update, delete
from db import engine, metadata, now_iso as _now_iso

# ── Config ────────────────────────────────────────────────────────────────────
ALLOWED_DOMAIN = "capillarytech.com"
ROLES          = ["Admin", "Campaign Manager", "Approver", "Viewer"]
COOKIE_NAME    = "mat_auth"

# Role hierarchy — higher index = fewer permissions
_ROLE_LEVEL = {r: i for i, r in enumerate(ROLES)}

# Shared engine; table registered on the shared metadata (see db.py)
_engine = engine

users = Table(
    "users", metadata,
    Column("email",       String, primary_key=True),
    Column("name",        String, nullable=False, default=""),
    Column("picture_url", String, nullable=False, default=""),
    Column("role",        String, nullable=False, default="Viewer"),
    # Stored as ISO string → portable across SQLite and Postgres, no dialect quirks
    Column("created_at",  String, nullable=False, default=""),
)


# ── User CRUD ─────────────────────────────────────────────────────────────────
def upsert_user(email: str, name: str, picture_url: str = "") -> None:
    """Insert a new user (role=Viewer) or update name/picture on re-login.
    Never changes an existing role."""
    with _engine.begin() as conn:
        existing = conn.execute(
            select(users.c.email).where(users.c.email == email)
        ).first()
        if existing:
            conn.execute(
                update(users).where(users.c.email == email)
                .values(name=name, picture_url=picture_url)
            )
        else:
            conn.execute(
                insert(users).values(
                    email=email, name=name, picture_url=picture_url,
                    role="Viewer", created_at=_now_iso(),
                )
            )


def get_user(email: str) -> dict | None:
    """Return user dict or None if not found."""
    with _engine.connect() as conn:
        row = conn.execute(
            select(users).where(users.c.email == email)
        ).mappings().first()
    return dict(row) if row else None


def get_all_users() -> list[dict]:
    """Return all users ordered by creation date."""
    with _engine.connect() as conn:
        rows = conn.execute(
            select(users).order_by(users.c.created_at)
        ).mappings().all()
    return [dict(r) for r in rows]


def set_role(email: str, role: str) -> None:
    """Assign a role to a user. Role must be in ROLES list."""
    if role not in ROLES:
        raise ValueError(f"Invalid role '{role}'. Must be one of {ROLES}")
    with _engine.begin() as conn:
        conn.execute(
            update(users).where(users.c.email == email).values(role=role)
        )


def delete_user(email: str) -> None:
    """Remove a user from the DB (Admin action)."""
    with _engine.begin() as conn:
        conn.execute(delete(users).where(users.c.email == email))


# ── Helpers ───────────────────────────────────────────────────────────────────
def is_allowed_domain(email: str) -> bool:
    return email.strip().lower().endswith(f"@{ALLOWED_DOMAIN}")


def has_permission(user: dict, min_role: str) -> bool:
    """True if user's role is at least as permissive as min_role."""
    return _ROLE_LEVEL.get(user.get("role", "Viewer"), 99) <= _ROLE_LEVEL.get(min_role, 0)


def role_badge_html(role: str) -> str:
    """Return a small coloured HTML badge for the given role."""
    colours = {
        "Admin":            ("#4F46E5", "#EEF2FF"),
        "Campaign Manager": ("#0369A1", "#E0F2FE"),
        "Approver":         ("#047857", "#ECFDF5"),
        "Viewer":           ("#6B7280", "#F3F4F6"),
    }
    fg, bg = colours.get(role, ("#6B7280", "#F3F4F6"))
    return (
        f"<span style='background:{bg};color:{fg};border:1px solid {fg}33;"
        f"border-radius:10px;padding:2px 9px;font-size:0.72rem;"
        f"font-weight:700;letter-spacing:0.04em;'>{role}</span>"
    )


# ── Signed session cookie (keeps users logged in across browser refreshes) ────
def _cookie_secret() -> str:
    return os.environ.get("COOKIE_SECRET", "mat_default_cookie_secret_change_me")


def sign_token(email: str) -> str:
    """Return a tamper-evident token `email|signature` for the session cookie."""
    sig = hmac.new(_cookie_secret().encode(), email.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{email}|{sig}"


def verify_token(token: str) -> str | None:
    """Return the email if the token's signature is valid and domain is allowed."""
    try:
        email, sig = token.rsplit("|", 1)
        expected = hmac.new(_cookie_secret().encode(), email.encode(), hashlib.sha256).hexdigest()[:32]
        if hmac.compare_digest(sig, expected) and is_allowed_domain(email):
            return email
    except Exception:
        pass
    return None
