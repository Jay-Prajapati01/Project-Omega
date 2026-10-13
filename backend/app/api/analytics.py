"""Consent-based, low-detail product analytics and owner-only summaries."""
from __future__ import annotations

from datetime import datetime, timezone
from contextlib import contextmanager
from pathlib import Path
import sqlite3
import threading
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, model_validator

from app.core.config import get_settings
from app.core.tenant import cloud, scope
from app.services.cloud_db import connect
from app.services import commerce

router = APIRouter(tags=["analytics"])
public_router = APIRouter(tags=["analytics"])
_local_schema_lock = threading.Lock()


@contextmanager
def _local_connection():
    path = Path(get_settings().data_dir) / "analytics.sqlite3"
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.execute("PRAGMA busy_timeout=10000")
    try:
        with _local_schema_lock:
            conn.execute("""CREATE TABLE IF NOT EXISTS analytics_events (
                visitor_key TEXT NOT NULL,
                event_name TEXT NOT NULL CHECK(event_name IN ('page_view','feature_used','heartbeat')),
                page_path TEXT NOT NULL,
                feature_key TEXT,
                occurred_at TEXT NOT NULL
            )""")
            conn.execute("CREATE INDEX IF NOT EXISTS analytics_events_time_idx ON analytics_events(occurred_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS analytics_events_page_idx ON analytics_events(page_path, occurred_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS analytics_events_feature_idx ON analytics_events(feature_key, occurred_at)")
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


class AnalyticsEvent(BaseModel):
    visitor_id: UUID
    event: Literal["page_view", "feature_used", "heartbeat"]
    path: Literal["/", "/contact", "/faq", "/privacy", "/dashboard", "/workspace", "/youtube", "/instagram", "/chat", "/graph", "/stored", "/profile", "/settings"]
    feature: Literal["youtube", "instagram", "ask_ai", "stored"] | None = None

    @model_validator(mode="after")
    def validate_feature(self):
        if (self.event == "feature_used") != (self.feature is not None):
            raise ValueError("Feature is required only for feature usage events.")
        return self


@public_router.post("/v1/analytics/events", status_code=202)
async def collect_event(payload: AnalyticsEvent):
    # Only coarse page/feature identifiers and a random browser UUID are kept.
    # No IP, account name, message, source URL, or user-supplied text is stored.
    if payload.event == "feature_used" and not payload.feature:
        raise HTTPException(422, "Feature is required for feature events.")
    try:
        if not cloud():
            with _local_connection() as conn:
                conn.execute(
                    "INSERT INTO analytics_events(visitor_key,event_name,page_path,feature_key,occurred_at) VALUES(?,?,?,?,?)",
                    (str(payload.visitor_id), payload.event, payload.path, payload.feature, datetime.now(timezone.utc).isoformat()),
                )
        else:
            with connect() as conn:
                conn.execute(
                    """INSERT INTO public.mm_analytics_events(visitor_key,event_name,page_path,feature_key)
                       VALUES(%s,%s,%s,%s)""",
                    (str(payload.visitor_id), payload.event, payload.path, payload.feature),
                )
                conn.commit()
    except Exception as exc:  # migration/DB availability is reported without leaking details
        raise HTTPException(503, "Analytics storage is unavailable. Apply the analytics migration and retry.") from exc
    return {"accepted": True}


@router.get("/v1/admin/analytics")
async def admin_analytics():
    scope()
    if commerce.entitlement()["role"] not in {"owner", "admin"}:
        raise HTTPException(403, "Admin access is required.")
    try:
        if not cloud():
            with _local_connection() as conn:
                totals = conn.execute("""SELECT
                    sum(CASE WHEN event_name='page_view' THEN 1 ELSE 0 END),
                    count(DISTINCT CASE WHEN event_name='page_view' AND occurred_at >= strftime('%Y-%m-%dT%H:%M:%S+00:00','now','-30 days') THEN visitor_key END),
                    count(DISTINCT CASE WHEN event_name='page_view' AND occurred_at >= strftime('%Y-%m-%dT%H:%M:%S+00:00','now','-24 hours') THEN visitor_key END),
                    count(DISTINCT CASE WHEN event_name='page_view' AND occurred_at >= strftime('%Y-%m-%dT%H:%M:%S+00:00','now','-7 days') THEN visitor_key END),
                    count(DISTINCT CASE WHEN occurred_at >= strftime('%Y-%m-%dT%H:%M:%S+00:00','now','-5 minutes') THEN visitor_key END)
                    FROM analytics_events""").fetchone()
                daily = conn.execute("""SELECT date(occurred_at), count(DISTINCT visitor_key)
                    FROM analytics_events WHERE event_name='page_view' AND occurred_at >= strftime('%Y-%m-%dT%H:%M:%S+00:00','now','-14 days')
                    GROUP BY date(occurred_at) ORDER BY date(occurred_at)""").fetchall()
                pages = conn.execute("""SELECT page_path,count(*),count(DISTINCT visitor_key) FROM analytics_events
                    WHERE event_name='page_view' AND occurred_at >= strftime('%Y-%m-%dT%H:%M:%S+00:00','now','-30 days')
                    GROUP BY page_path ORDER BY count(*) DESC LIMIT 20""").fetchall()
                features = conn.execute("""SELECT feature_key,count(*),count(DISTINCT visitor_key) FROM analytics_events
                    WHERE event_name='feature_used' AND occurred_at >= strftime('%Y-%m-%dT%H:%M:%S+00:00','now','-30 days')
                    GROUP BY feature_key ORDER BY count(*) DESC""").fetchall()
                all_time = conn.execute("SELECT count(DISTINCT visitor_key) FROM analytics_events WHERE event_name='page_view'").fetchone()[0]
        else:
            with connect() as conn:
                totals = conn.execute("""SELECT
                count(*) FILTER (WHERE event_name='page_view') AS page_views,
                count(DISTINCT visitor_key) FILTER (WHERE event_name='page_view' AND occurred_at >= now()-interval '30 days') AS visitors,
                count(DISTINCT visitor_key) FILTER (WHERE event_name='page_view' AND occurred_at >= now()-interval '24 hours') AS visitors_24h,
                count(DISTINCT visitor_key) FILTER (WHERE event_name='page_view' AND occurred_at >= now()-interval '7 days') AS visitors_7d,
                count(DISTINCT visitor_key) FILTER (WHERE occurred_at >= now()-interval '5 minutes') AS online_now
                    FROM public.mm_analytics_events""").fetchone()
                daily = conn.execute("""SELECT to_char(day,'YYYY-MM-DD'), visitors FROM (
                SELECT date_trunc('day',occurred_at AT TIME ZONE 'UTC') AS day, count(DISTINCT visitor_key) AS visitors
                FROM public.mm_analytics_events WHERE event_name='page_view' AND occurred_at >= now()-interval '14 days'
                    GROUP BY 1) d ORDER BY day""").fetchall()
                pages = conn.execute("""SELECT page_path, count(*) AS views, count(DISTINCT visitor_key) AS visitors
                FROM public.mm_analytics_events WHERE event_name='page_view' AND occurred_at >= now()-interval '30 days'
                    GROUP BY page_path ORDER BY views DESC LIMIT 20""").fetchall()
                features = conn.execute("""SELECT feature_key, count(*) AS uses, count(DISTINCT visitor_key) AS users
                FROM public.mm_analytics_events WHERE event_name='feature_used' AND occurred_at >= now()-interval '30 days'
                    GROUP BY feature_key ORDER BY uses DESC""").fetchall()
                all_time = conn.execute("SELECT count(DISTINCT visitor_key) FROM public.mm_analytics_events WHERE event_name='page_view'").fetchone()[0]
    except Exception as exc:
        raise HTTPException(503, "Analytics storage is unavailable. Apply the analytics migration.") from exc
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "totals": {"all_time_visitors": int(all_time or 0), "visitors_24h": int(totals[2] or 0), "visitors_7d": int(totals[3] or 0), "online_now": int(totals[4] or 0), "page_views": int(totals[0] or 0), "visitors_30d": int(totals[1] or 0)},
        "daily": [{"date": row[0], "visitors": int(row[1])} for row in daily],
        "pages": [{"path": row[0], "views": int(row[1]), "visitors": int(row[2])} for row in pages],
        "features": [{"feature": row[0], "uses": int(row[1]), "users": int(row[2])} for row in features],
        "window": "30 days for pages/features; 14 days for daily visitors; online means active in the last 5 minutes",
    }
