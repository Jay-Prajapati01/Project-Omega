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


@router.get("/v1/admin/api-key-analytics")
async def admin_api_key_analytics():
    """Platform-admin-only, prompt-free provider usage and quota telemetry."""
    scope()
    if commerce.entitlement()["role"] not in {"owner", "admin"}:
        raise HTTPException(403, "Admin access is required.")
    settings = get_settings()
    mode = settings.mindmesh_execution_mode
    provider = settings.llm_provider or ("ollama" if mode == "local" else "unconfigured")
    model = settings.groq_model if provider == "groq" else settings.xai_model if provider == "xai" else settings.llm_model
    if not cloud():
        return {"mode": mode, "provider": provider, "model": model, "recording": False,
                "message": "Local mode is using Ollama. No external API-key usage is being recorded in this environment.",
                "totals": {}, "by_task": [], "recent": []}
    try:
        with connect() as conn:
            totals = conn.execute("""select count(*), count(*) filter(where status='success'),
                count(*) filter(where status<>'success'), coalesce(sum(input_tokens),0),
                coalesce(sum(output_tokens),0), coalesce(sum(total_tokens),0),
                coalesce(avg(latency_ms),0), count(*) filter(where status='rate_limited'),
                coalesce(sum(retry_count),0), count(distinct request_id) filter(where fallback_used)
                from public.mm_llm_usage_events where created_at >= now()-interval '24 hours'""").fetchone()
            by_task = conn.execute("""select task_type,count(*),count(*) filter(where status='success'),
                count(*) filter(where status='rate_limited') from public.mm_llm_usage_events
                where created_at >= now()-interval '30 days' group by task_type order by count(*) desc""").fetchall()
            quota = conn.execute("""select created_at, model, quota_scope, rpd_limit, rpd_remaining, rpd_reset,
                tpm_limit, tpm_remaining, tpm_reset from public.mm_llm_usage_events
                where rpd_limit is not null or rpd_remaining is not null or tpm_limit is not null or tpm_remaining is not null
                order by created_at desc limit 1""").fetchone()
            key_stats = conn.execute("""select key_alias, max(provider), max(model), count(*),
                count(*) filter(where status='success'), count(*) filter(where status<>'success'),
                coalesce(sum(total_tokens),0), max(created_at), count(*) filter(where status='auth_error')
                from public.mm_llm_usage_events where created_at >= now()-interval '30 days'
                group by key_alias order by key_alias""").fetchall()
            recent = conn.execute("""select created_at,request_id,task_type,provider,model,key_alias,quota_scope,
                status,http_status,latency_ms,input_tokens,output_tokens,total_tokens,retry_count,
                fallback_used,fallback_reason,error_code,rpd_limit,rpd_remaining,rpd_reset,
                tpm_limit,tpm_remaining,tpm_reset from public.mm_llm_usage_events
                order by created_at desc limit 100""").fetchall()
        columns = ("created_at request_id task_type provider model key_alias quota_scope status http_status latency_ms "
                   "input_tokens output_tokens total_tokens retry_count fallback_used fallback_reason error_code "
                   "rpd_limit rpd_remaining rpd_reset tpm_limit tpm_remaining tpm_reset").split()
        return {"mode": mode, "provider": provider, "model": model, "recording": True,
                "quota_scope_note": "Per-alias figures are attributed call activity and token usage, not a separate quota. Groq limits are shared at organization/project and model scope.",
                "totals": {"attempts_24h": totals[0], "successes_24h": totals[1], "failures_24h": totals[2],
                           "input_tokens_24h": totals[3], "output_tokens_24h": totals[4], "total_tokens_24h": totals[5],
                           "average_latency_ms_24h": round(float(totals[6] or 0)), "rate_limits_24h": totals[7],
                           "retries_24h": totals[8], "fallbacks_24h": totals[9]},
                "by_task_30d": [{"task_type": r[0], "attempts": r[1], "successes": r[2], "rate_limits": r[3]} for r in by_task],
                "keys": [{"alias": r[0], "provider": r[1], "model": r[2],
                          "attempts_30d": r[3], "successes_30d": r[4], "failures_30d": r[5],
                          "tokens_30d": r[6], "last_used_at": r[7],
                          "auth_failures_30d": r[8], "health": "credential_error" if r[8] else "observed"}
                         for r in key_stats],
                "quota_snapshot": ({"observed_at": quota[0], "model": quota[1], "scope": quota[2],
                                    "source": "response_header", "requests_per_day_limit": quota[3],
                                    "requests_per_day_remaining": quota[4], "requests_per_day_reset": quota[5],
                                    "tokens_per_minute_limit": quota[6], "tokens_per_minute_remaining": quota[7],
                                    "tokens_per_minute_reset": quota[8]} if quota else None),
                "recent": [dict(zip(columns, row)) for row in recent]}
    except Exception as exc:
        raise HTTPException(503, "Provider analytics storage is unavailable. Apply the LLM usage migration.") from exc
