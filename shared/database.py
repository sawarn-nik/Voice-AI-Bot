"""
SQLite Lead Store
=================
Replaces in-memory dict for CRM storage.
Leads persist across server restarts.
Uses SQLAlchemy Core (no ORM) for simplicity.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from sqlalchemy import (
    create_engine, Table, Column, MetaData,
    String, Integer, Boolean, Float, Text, DateTime,
    select, insert, update
)

from shared.utils import logger

DB_PATH = Path(__file__).parent.parent / "darwix.db"
DB_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DB_URL, echo=False)
metadata = MetaData()

leads_table = Table(
    "leads", metadata,
    Column("session_id",            String(64), primary_key=True),
    Column("name",                  String(200)),
    Column("age",                   Integer),
    Column("smoker",                Boolean),
    Column("has_preexisting",       Boolean),
    Column("bmi_over_40",           Boolean),
    Column("num_dependents",        Integer, default=0),
    Column("monthly_budget_php",    Integer),
    Column("contact_number",        String(20)),
    Column("email",                 String(200)),
    Column("callback_time",         String(200)),
    Column("plan_interest",         String(50)),
    Column("outcome",               String(30), default="IN_PROGRESS"),
    Column("turns",                 Integer, default=0),
    Column("market",                String(10), default="EN"),
    Column("call_transcript",       Text),
    Column("created_at",            DateTime, default=datetime.utcnow),
    Column("updated_at",            DateTime, default=datetime.utcnow),
)


def init_db() -> None:
    """Create tables if they don't exist."""
    metadata.create_all(engine)
    logger.info("db_initialized", path=str(DB_PATH))


def upsert_lead(payload: dict) -> None:
    """Insert or update a lead record by session_id."""
    payload["updated_at"] = datetime.utcnow()

    with engine.begin() as conn:
        existing = conn.execute(
            select(leads_table).where(leads_table.c.session_id == payload["session_id"])
        ).fetchone()

        # Map CRM dict keys to column names
        row = {
            "session_id":         payload.get("session_id"),
            "name":               payload.get("name"),
            "age":                payload.get("age"),
            "smoker":             payload.get("smoker"),
            "has_preexisting":    payload.get("has_preexisting_conditions"),
            "bmi_over_40":        payload.get("bmi_flag"),
            "num_dependents":     payload.get("dependents", 0),
            "monthly_budget_php": payload.get("monthly_budget_php"),
            "contact_number":     payload.get("contact_number"),
            "email":              payload.get("email"),
            "callback_time":      payload.get("callback_time"),
            "plan_interest":      payload.get("plan_interest"),
            "outcome":            payload.get("outcome", "IN_PROGRESS"),
            "turns":              payload.get("turns", 0),
            "updated_at":         payload["updated_at"],
        }

        if existing:
            conn.execute(
                update(leads_table)
                .where(leads_table.c.session_id == payload["session_id"])
                .values(**{k: v for k, v in row.items() if v is not None})
            )
        else:
            row["created_at"] = datetime.utcnow()
            conn.execute(insert(leads_table).values(**row))

    logger.info("lead_upserted", session_id=payload.get("session_id"), outcome=payload.get("outcome"))


def get_all_leads() -> List[dict]:
    """Return all leads as list of dicts."""
    with engine.connect() as conn:
        rows = conn.execute(select(leads_table).order_by(leads_table.c.updated_at.desc())).fetchall()
    return [dict(row._mapping) for row in rows]


def get_lead(session_id: str) -> Optional[dict]:
    with engine.connect() as conn:
        row = conn.execute(
            select(leads_table).where(leads_table.c.session_id == session_id)
        ).fetchone()
    return dict(row._mapping) if row else None


# Initialize on import
init_db()
