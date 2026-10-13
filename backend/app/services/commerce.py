"""Server-authoritative plans, promos, usage and BYOK credential metadata.

The API never accepts a plan, role or quota from the client. Cloud deployments
use the commerce migration's PostgreSQL tables; authenticated local development
uses a per-user JSON file so the web and Android companion share the same rules.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.tenant import cloud, current_scope, data_directory, scope
from app.services.cloud_db import connect

FEATURES = ("youtube", "instagram", "pdf", "documents", "audio", "web", "search", "chat")
PLANS: dict[str, dict[str, Any]] = {
    "free": {"name": "Free", "price_paise": 0, "limits": dict(zip(FEATURES, (3, 5, 5, 10, 3, 10, 50, 25)))},
    "plus": {"name": "Plus", "price_paise": 29900, "limits": dict(zip(FEATURES, (20, 30, 30, 50, 20, 60, 500, 200)))},
    "pro": {"name": "Pro", "price_paise": 79900, "limits": dict(zip(FEATURES, (60, 100, 100, 150, 60, 200, 2000, 800)))},
}
PLAN_RANK = {"free": 0, "plus": 1, "pro": 2}


class CommerceError(ValueError):
    def __init__(self, code: str, message: str, status: int = 422):
        super().__init__(message)
        self.code, self.status = code, status


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _period() -> str:
    return _now().strftime("%Y-%m")


def _local_path() -> Path:
    folder = data_directory()
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "commerce.json"


def _local_promos_path() -> Path:
    """Shared development-only promo store.

    Production always uses Supabase. Local Docker development needs one shared
    store so an administrator can create a campaign and a different signed-in
    user can redeem it without sharing either user's private data file.
    """
    folder = Path(get_settings().data_dir)
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "admin-promos.json"


def _local_promos() -> dict:
    path = _local_promos_path()
    if not path.exists():
        return {"promos": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data.get("promos"), list) else {"promos": []}
    except (OSError, json.JSONDecodeError):
        return {"promos": []}


def _save_local_promos(data: dict) -> None:
    path = _local_promos_path()
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2), encoding="utf-8")
    temporary.replace(path)


def _local() -> dict:
    path = _local_path()
    default = {"subscription": {"base_plan": "free", "status": "active"}, "usage": {}, "credentials": {}, "preferences": {}, "grants": [], "roles": ["member"]}
    if not path.exists():
        return default
    try:
        return {**default, **json.loads(path.read_text(encoding="utf-8"))}
    except (OSError, json.JSONDecodeError):
        return default


def _save_local(data: dict) -> None:
    path = _local_path()
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2), encoding="utf-8")
    temporary.replace(path)


def plan_catalog() -> list[dict]:
    return [{"key": key, "name": values["name"], "price_paise": values["price_paise"], "currency": "INR", "limits": values["limits"]} for key, values in PLANS.items()]


def bootstrap_account() -> None:
    """Create the default server-owned account rows idempotently."""
    if not cloud():
        state = _local()
        # The configured UUID is the only local-development bootstrap route.
        # It must match a real authenticated Supabase user; email and promos
        # never confer an administrative role. Anonymous local users simply
        # have no scope, so resolve it defensively instead of 403ing them.
        owner_bootstrap = get_settings().owner_bootstrap_user_id
        current = current_scope.get()
        if owner_bootstrap and current is not None and owner_bootstrap == current.user_id:
            state["roles"] = sorted(set(state.get("roles", []) + ["owner"]))
        _save_local(state)
        return
    user = scope().user_id
    with connect() as conn:
        conn.execute("INSERT INTO public.mm_profiles(user_id) VALUES (%s) ON CONFLICT(user_id) DO NOTHING", (user,))
        conn.execute("INSERT INTO public.mm_subscriptions(user_id) VALUES (%s) ON CONFLICT(user_id) DO NOTHING", (user,))
        conn.execute("INSERT INTO public.mm_user_roles(user_id,role) VALUES (%s,'member') ON CONFLICT(user_id,role) DO NOTHING", (user,))
        # Owner access comes only from a deployment secret bound to an already
        # authenticated Supabase UUID. No email/password or promo can grant it.
        if get_settings().owner_bootstrap_user_id == user:
            conn.execute("INSERT INTO public.mm_user_roles(user_id,role,granted_by) VALUES (%s,'owner',%s) ON CONFLICT(user_id,role) DO UPDATE SET revoked_at=NULL", (user, user))
        conn.commit()


def _cloud_state() -> tuple[str, list[str], list[dict]]:
    bootstrap_account()
    user = scope().user_id
    with connect() as conn:
        subscription = conn.execute("SELECT base_plan FROM public.mm_subscriptions WHERE user_id=%s", (user,)).fetchone()
        roles = [row[0] for row in conn.execute("SELECT role FROM public.mm_user_roles WHERE user_id=%s AND revoked_at IS NULL", (user,)).fetchall()]
        grants = conn.execute("""SELECT id::text,plan_key,cohort,expires_at FROM public.mm_access_grants
            WHERE user_id=%s AND revoked_at IS NULL AND starts_at <= now() AND expires_at > now()""", (user,)).fetchall()
    return (subscription[0] if subscription else "free", roles or ["member"], [{"id": x[0], "plan": x[1], "cohort": x[2], "expires_at": x[3].isoformat()} for x in grants])


def entitlement() -> dict:
    bootstrap_account()
    if cloud():
        base, roles, grants = _cloud_state()
    else:
        state = _local()
        base = state["subscription"].get("base_plan", "free")
        roles = state.get("roles", ["member"])
        grants = [g for g in state.get("grants", []) if g.get("expires_at", "") > _now().isoformat() and not g.get("revoked")]
    effective = base if base in PLANS else "free"
    for grant in grants:
        candidate = grant.get("plan", "free")
        if PLAN_RANK.get(candidate, -1) > PLAN_RANK[effective]:
            effective = candidate
    role = "owner" if "owner" in roles else "admin" if "admin" in roles else "member"
    usage = get_usage(effective)
    return {"role": role, "base_plan": base, "effective_plan": effective, "beta_tester": any(g.get("cohort") == "beta_tester" for g in grants), "grants": grants, "usage": usage, "period": _period(), "ai_mode": provider_mode()}


def get_usage(plan: str | None = None) -> dict[str, dict]:
    # Identity is only needed for per-user cloud counters. The anonymous
    # local workspace shares one JSON quota file, so resolving scope here
    # would 403 every metered endpoint for signed-out local users.
    period = _period()
    used: dict[str, int] = {}
    if cloud():
        user = scope().user_id
        bootstrap_account()
        with connect() as conn:
            rows = conn.execute("SELECT feature_key,consumed FROM public.mm_usage_counters WHERE user_id=%s AND period_key=%s", (user, period)).fetchall()
        used = {key: int(count) for key, count in rows}
    else:
        used = _local().get("usage", {}).get(period, {})
    selected = plan or entitlement()["effective_plan"]
    limits = PLANS[selected]["limits"]
    return {key: {"used": int(used.get(key, 0)), "limit": value, "remaining": max(0, value - int(used.get(key, 0)))} for key, value in limits.items()}


def reserve(feature: str, idempotency_key: str = "") -> dict:
    """Atomically charge one accepted feature action. Call before expensive work."""
    if feature not in FEATURES:
        raise CommerceError("UNKNOWN_FEATURE", "Unsupported metered feature")
    ent = entitlement()
    limit = PLANS[ent["effective_plan"]]["limits"][feature]
    # Same as get_usage: the local quota file is shared, so identity is
    # only resolved for per-user cloud counters (middleware guarantees a
    # scope there; anonymous local users must not 403 here).
    period = _period()
    if ent["role"] == "owner":
        return {"provider": provider_mode(), "feature": feature, "owner_access": True}
    if cloud():
        user = scope().user_id
        with connect() as conn:
            row = conn.execute("""INSERT INTO public.mm_usage_counters(user_id,feature_key,period_key,consumed)
              VALUES(%s,%s,%s,1) ON CONFLICT(user_id,feature_key,period_key)
              DO UPDATE SET consumed=public.mm_usage_counters.consumed+1, updated_at=now()
              WHERE public.mm_usage_counters.consumed < %s RETURNING consumed""", (user, feature, period, limit)).fetchone()
            if not row:
                conn.rollback()
                raise CommerceError("QUOTA_EXCEEDED", f"Your {PLANS[ent['effective_plan']]['name']} plan has reached its {feature} allowance.", 429)
            conn.commit()
    else:
        state = _local()
        usage = state.setdefault("usage", {}).setdefault(period, {})
        current = int(usage.get(feature, 0))
        if current >= limit:
            raise CommerceError("QUOTA_EXCEEDED", f"Your {PLANS[ent['effective_plan']]['name']} plan has reached its {feature} allowance.", 429)
        usage[feature] = current + 1
        _save_local(state)
    return {"provider": provider_mode(), "feature": feature, "plan": ent["effective_plan"]}


def _pepper() -> bytes:
    value = get_settings().promo_hmac_pepper
    if not value:
        raise CommerceError("PROMOS_NOT_CONFIGURED", "Promo redemption is not configured.", 503)
    return value.encode()


def _code_hmac(code: str) -> str:
    return hmac.new(_pepper(), code.strip().upper().encode(), hashlib.sha256).hexdigest()


def _require_admin() -> None:
    if entitlement()["role"] not in {"owner", "admin"}:
        raise CommerceError("FORBIDDEN", "Admin access is required.", 403)


def _audit(action: str, target: str = "", details: dict | None = None) -> None:
    if cloud():
        with connect() as conn:
            conn.execute("INSERT INTO public.mm_admin_audit_logs(actor_id,action,target_id,details) VALUES(%s,%s,%s,%s)", (scope().user_id, action, target, json.dumps(details or {})))
            conn.commit()


def create_promo(payload: dict) -> dict:
    _require_admin()
    allowed = sorted(set(payload.get("allowed_plans", [])))
    if not allowed or any(p not in PLANS for p in allowed):
        raise CommerceError("INVALID_POLICY", "Choose one or more valid plan grants.")
    duration = int(payload.get("duration_hours", 0))
    if not 1 <= duration <= 8760:
        raise CommerceError("INVALID_POLICY", "Duration must be from one hour to one year.")
    code = payload.get("code", "").strip().upper() or "MM-" + secrets.token_urlsafe(18).upper().replace("_", "").replace("-", "")
    if len(code) < 12 or len(code) > 80:
        raise CommerceError("INVALID_CODE", "Promo codes must be 12 to 80 characters.")
    if not cloud():
        state = _local_promos()
        if any(item.get("code_hmac") == _code_hmac(code) for item in state["promos"]):
            raise CommerceError("DUPLICATE_CODE", "That promo code already exists.", 409)
        promo_id = secrets.token_hex(16)
        state["promos"].append({
            "id": promo_id, "code_hmac": _code_hmac(code), "preview_prefix": code[:6] + "…",
            "campaign_name": payload.get("campaign_name", "Campaign")[:120],
            "description": payload.get("description", "")[:500], "kind": payload.get("kind", "plan_grant"),
            "allowed_plans": allowed, "duration_hours": duration, "status": "active",
            "starts_at": _now().isoformat(), "redeem_until": payload.get("redeem_until") or None,
            "max_total_redemptions": payload.get("max_total_redemptions") or None,
            "max_per_user": max(1, int(payload.get("max_per_user", 1))), "redemptions": [],
        })
        _save_local_promos(state)
        return {"id": promo_id, "code": code, "preview_prefix": code[:6] + "…"}
    with connect() as conn:
        row = conn.execute("""INSERT INTO public.mm_promo_codes(code_hmac,preview_prefix,campaign_name,description,kind,allowed_plans,duration_hours,redeem_until,max_total_redemptions,max_per_user,created_by)
          VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id::text""", (_code_hmac(code), code[:6] + "…", payload.get("campaign_name", "Campaign")[:120], payload.get("description", "")[:500], payload.get("kind", "plan_grant"), allowed, duration, payload.get("redeem_until") or None, payload.get("max_total_redemptions") or None, max(1, int(payload.get("max_per_user", 1))), scope().user_id)).fetchone()
        conn.commit()
    _audit("promo.created", row[0], {"campaign": payload.get("campaign_name", "Campaign")})
    return {"id": row[0], "code": code, "preview_prefix": code[:6] + "…"}


def list_promos() -> list[dict]:
    _require_admin()
    if not cloud():
        return [{"id": item["id"], "prefix": item["preview_prefix"], "campaign_name": item["campaign_name"],
                 "kind": item["kind"], "allowed_plans": item["allowed_plans"], "duration_hours": item["duration_hours"],
                 "status": item["status"], "starts_at": item["starts_at"], "redeem_until": item.get("redeem_until"),
                 "max_total_redemptions": item.get("max_total_redemptions"), "redemptions": len(item.get("redemptions", []))}
                for item in _local_promos()["promos"]]
    with connect() as conn:
        rows = conn.execute("""SELECT p.id::text,p.preview_prefix,p.campaign_name,p.kind,p.allowed_plans,p.duration_hours,p.status,p.starts_at,p.redeem_until,p.max_total_redemptions,count(r.id)
          FROM public.mm_promo_codes p LEFT JOIN public.mm_promo_redemptions r ON r.promo_id=p.id GROUP BY p.id ORDER BY p.created_at DESC""").fetchall()
    return [{"id":r[0],"prefix":r[1],"campaign_name":r[2],"kind":r[3],"allowed_plans":r[4],"duration_hours":r[5],"status":r[6],"starts_at":r[7].isoformat(),"redeem_until":r[8].isoformat() if r[8] else None,"max_total_redemptions":r[9],"redemptions":r[10]} for r in rows]


def preview_promo(code: str) -> dict:
    if not cloud():
        item = next((p for p in _local_promos()["promos"] if hmac.compare_digest(p.get("code_hmac", ""), _code_hmac(code))), None)
        if not item:
            raise CommerceError("INVALID_CODE", "That promo code is not valid.")
        if item.get("status") != "active":
            raise CommerceError("REVOKED", "That promo code is unavailable.")
        now = _now()
        if item.get("redeem_until") and item["redeem_until"] <= now.isoformat():
            raise CommerceError("EXPIRED", "That promo code has expired.")
        if item.get("max_total_redemptions") and len(item.get("redemptions", [])) >= int(item["max_total_redemptions"]):
            raise CommerceError("CAP_REACHED", "That promo campaign has reached capacity.")
        return {"promo_id": item["id"], "campaign_name": item["campaign_name"], "kind": item["kind"], "allowed_plans": item["allowed_plans"], "duration_hours": item["duration_hours"]}
    with connect() as conn:
        row = conn.execute("SELECT id::text,campaign_name,kind,allowed_plans,duration_hours,status,starts_at,redeem_until,max_total_redemptions FROM public.mm_promo_codes WHERE code_hmac=%s", (_code_hmac(code),)).fetchone()
        if not row:
            raise CommerceError("INVALID_CODE", "That promo code is not valid.")
        count = conn.execute("SELECT count(*) FROM public.mm_promo_redemptions WHERE promo_id=%s", (row[0],)).fetchone()[0]
    if row[5] != "active":
        raise CommerceError("REVOKED", "That promo code is unavailable.")
    now = _now()
    if row[6] > now:
        raise CommerceError("NOT_YET_ACTIVE", "That promo code is not active yet.")
    if row[7] and row[7] <= now:
        raise CommerceError("EXPIRED", "That promo code has expired.")
    if row[8] and count >= row[8]:
        raise CommerceError("CAP_REACHED", "That promo campaign has reached capacity.")
    return {"promo_id": row[0], "campaign_name": row[1], "kind": row[2], "allowed_plans": row[3], "duration_hours": row[4]}


def redeem_promo(code: str, selected_plan: str) -> dict:
    preview = preview_promo(code)
    if selected_plan not in preview["allowed_plans"]:
        raise CommerceError("NOT_ELIGIBLE", "Select a plan offered by this promo.")
    user = scope().user_id
    if not cloud():
        data = _local_promos()
        item = next(p for p in data["promos"] if p["id"] == preview["promo_id"])
        user = scope().user_id
        if user in item.get("redemptions", []):
            raise CommerceError("REDEEMED", "You have already redeemed this promo.", 409)
        item.setdefault("redemptions", []).append(user)
        _save_local_promos(data)
        state = _local()
        from datetime import timedelta
        expires_at = (_now() + timedelta(hours=item["duration_hours"])).isoformat()
        state.setdefault("grants", []).append({"id": secrets.token_hex(16), "plan": selected_plan,
                                                 "cohort": "beta_tester" if item["kind"] == "beta_grant" else None,
                                                 "expires_at": expires_at, "revoked": False})
        _save_local(state)
        return {"effective_plan": entitlement()["effective_plan"], "expires_at": expires_at, "message": "Promo applied to your account."}
    with connect() as conn:
        try:
            row = conn.execute("SELECT id,duration_hours,kind FROM public.mm_promo_codes WHERE id=%s FOR UPDATE", (preview["promo_id"],)).fetchone()
            redemption = conn.execute("INSERT INTO public.mm_promo_redemptions(promo_id,user_id,chosen_plan) VALUES(%s,%s,%s) RETURNING id", (row[0], user, selected_plan)).fetchone()
            grant = conn.execute("""INSERT INTO public.mm_access_grants(user_id,promo_id,redemption_id,plan_key,cohort,expires_at)
              VALUES(%s,%s,%s,%s,%s,now() + (%s || ' hours')::interval) RETURNING expires_at""", (user, row[0], redemption[0], selected_plan, "beta_tester" if row[2] == "beta_grant" else None, row[1])).fetchone()
            conn.commit()
        except Exception as exc:
            conn.rollback()
            if "unique" in str(exc).lower():
                raise CommerceError("REDEEMED", "You have already redeemed this promo.", 409) from None
            raise
    return {"effective_plan": entitlement()["effective_plan"], "expires_at": grant[0].isoformat(), "message": "Promo applied to your account."}


def _encryption_key() -> bytes:
    raw = get_settings().byok_encryption_key
    if not raw:
        raise CommerceError("BYOK_NOT_CONFIGURED", "Secure provider-key storage is not configured.", 503)
    try:
        key = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
    except Exception as exc:
        raise CommerceError("BYOK_NOT_CONFIGURED", "Provider-key encryption is misconfigured.", 503) from exc
    if len(key) != 32:
        raise CommerceError("BYOK_NOT_CONFIGURED", "Provider-key encryption requires a 32-byte key.", 503)
    return key


def _encrypt(value: str) -> tuple[bytes, bytes]:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    nonce = os.urandom(12)
    return AESGCM(_encryption_key()).encrypt(nonce, value.encode(), scope().user_id.encode()), nonce


async def validate_provider_key(provider: str, key: str) -> None:
    if provider == "groq":
        url, headers = "https://api.groq.com/openai/v1/models", {"Authorization": f"Bearer {key}"}
    elif provider == "gemini":
        url, headers = "https://generativelanguage.googleapis.com/v1beta/models", {"x-goog-api-key": key}
    else:
        raise CommerceError("UNSUPPORTED_PROVIDER", "Supported providers are Groq and Gemini.")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url, headers=headers)
    except httpx.HTTPError as exc:
        raise CommerceError("PROVIDER_UNAVAILABLE", "Could not reach the provider. Try again shortly.", 503) from exc
    if response.status_code in {401, 403}:
        raise CommerceError("INVALID_KEY", "The provider rejected that key.")
    if response.status_code >= 400:
        raise CommerceError("PROVIDER_UNAVAILABLE", "The provider could not validate the key.", 503)


async def save_provider_key(provider: str, key: str) -> dict:
    if len(key.strip()) < 12:
        raise CommerceError("INVALID_KEY", "Enter a valid provider API key.")
    await validate_provider_key(provider, key.strip())
    ciphertext, nonce = _encrypt(key.strip())
    if cloud():
        with connect() as conn:
            conn.execute("""INSERT INTO public.mm_ai_credentials(user_id,provider,ciphertext,nonce,key_version,last4,status,verified_at)
              VALUES(%s,%s,%s,%s,'v1',%s,'verified',now()) ON CONFLICT(user_id,provider) DO UPDATE SET ciphertext=excluded.ciphertext,nonce=excluded.nonce,key_version='v1',last4=excluded.last4,status='verified',verified_at=now(),updated_at=now()""", (scope().user_id,provider,ciphertext,nonce,key.strip()[-4:]))
            conn.commit()
    else:
        state = _local()
        state.setdefault("credentials", {})[provider] = {"last4": key.strip()[-4:], "status":"verified", "verified_at":_now().isoformat()}
        _save_local(state)
    return {"provider": provider, "masked_key": "••••" + key.strip()[-4:], "status":"verified", "verified_at": _now().isoformat()}


def list_provider_keys() -> list[dict]:
    if cloud():
        with connect() as conn:
            rows = conn.execute("SELECT provider,last4,status,verified_at,updated_at FROM public.mm_ai_credentials WHERE user_id=%s", (scope().user_id,)).fetchall()
        return [{"provider":r[0],"masked_key":"••••"+r[1],"status":r[2],"verified_at":r[3].isoformat() if r[3] else None,"updated_at":r[4].isoformat()} for r in rows]
    return [{"provider":provider,"masked_key":"••••"+row["last4"],"status":row["status"],"verified_at":row.get("verified_at")} for provider,row in _local().get("credentials",{}).items()]


def remove_provider_key(provider: str) -> None:
    if provider not in {"groq", "gemini"}:
        raise CommerceError("UNSUPPORTED_PROVIDER", "Unsupported provider.")
    if cloud():
        with connect() as conn:
            conn.execute("DELETE FROM public.mm_ai_credentials WHERE user_id=%s AND provider=%s", (scope().user_id,provider))
            conn.execute("UPDATE public.mm_provider_preferences SET mode='managed',fallback_to_managed=false WHERE user_id=%s AND provider=%s", (scope().user_id,provider))
            conn.commit()
    else:
        state = _local()
        state.get("credentials",{}).pop(provider,None)
        _save_local(state)


def set_preferences(preferences: list[dict]) -> list[dict]:
    valid = {"llm":"groq", "embeddings":"gemini", "transcription":"groq"}
    for item in preferences:
        purpose, mode, provider = item.get("purpose"), item.get("mode"), item.get("provider")
        if purpose not in valid or mode not in {"managed","byok"} or provider != valid[purpose]:
            raise CommerceError("INVALID_PREFERENCES", "Invalid provider routing.")
        if mode == "byok" and provider not in {key["provider"] for key in list_provider_keys()}:
            raise CommerceError("MISSING_KEY", f"Connect your {provider.title()} key before enabling BYOK.")
    if cloud():
        with connect() as conn:
            for item in preferences:
                conn.execute("INSERT INTO public.mm_provider_preferences(user_id,purpose,mode,provider,fallback_to_managed) VALUES(%s,%s,%s,%s,%s) ON CONFLICT(user_id,purpose) DO UPDATE SET mode=excluded.mode,provider=excluded.provider,fallback_to_managed=excluded.fallback_to_managed", (scope().user_id,item["purpose"],item["mode"],item["provider"],bool(item.get("fallback_to_managed",False))))
            conn.commit()
    else:
        state=_local()
        state["preferences"]={i["purpose"]:i for i in preferences}
        _save_local(state)
    return provider_preferences()


def provider_preferences() -> list[dict]:
    defaults = [{"purpose":"llm","provider":"groq","mode":"managed","fallback_to_managed":False},{"purpose":"embeddings","provider":"gemini","mode":"managed","fallback_to_managed":False},{"purpose":"transcription","provider":"groq","mode":"managed","fallback_to_managed":False}]
    if cloud():
        with connect() as conn:
            rows=conn.execute("SELECT purpose,provider,mode,fallback_to_managed FROM public.mm_provider_preferences WHERE user_id=%s",(scope().user_id,)).fetchall()
        found={r[0]:{"purpose":r[0],"provider":r[1],"mode":r[2],"fallback_to_managed":r[3]} for r in rows}
    else:
        found=_local().get("preferences",{})
    return [found.get(item["purpose"],item) for item in defaults]


def provider_mode() -> str:
    return "byok" if any(item["mode"] == "byok" for item in provider_preferences()) else "managed"

