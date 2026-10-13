"""Authenticated commerce, entitlement, BYOK and administration endpoints."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.services import commerce

router = APIRouter(tags=["commerce"])
public_router = APIRouter(tags=["commerce"])


def _error(exc: commerce.CommerceError) -> HTTPException:
    return HTTPException(exc.status, {"code": exc.code, "message": str(exc)})


class PromoInput(BaseModel):
    code: str = Field(min_length=1, max_length=80)


class PromoRedeem(PromoInput):
    selected_plan: Literal["free", "plus", "pro"]


class ProviderKey(BaseModel):
    key: str = Field(min_length=12, max_length=512)


class ProviderPreference(BaseModel):
    purpose: Literal["llm", "embeddings", "transcription"]
    provider: Literal["groq", "gemini"]
    mode: Literal["managed", "byok"]
    fallback_to_managed: bool = False


class Preferences(BaseModel):
    preferences: list[ProviderPreference] = Field(min_length=1, max_length=3)


class PromoCreate(BaseModel):
    campaign_name: str = Field(min_length=3, max_length=120)
    description: str = Field(default="", max_length=500)
    code: str = Field(default="", max_length=80)
    kind: Literal["plan_grant", "beta_grant"] = "plan_grant"
    allowed_plans: list[Literal["free", "plus", "pro"]]
    duration_hours: int = Field(ge=1, le=8760)
    redeem_until: str | None = None
    max_total_redemptions: int | None = Field(default=None, ge=1, le=100000)
    max_per_user: int = Field(default=1, ge=1, le=10)


@public_router.get("/v1/public/plans")
async def plans():
    return {"plans": commerce.plan_catalog(), "payment_enabled": False}


@router.get("/v1/me/entitlements")
async def entitlements():
    try:
        return commerce.entitlement()
    except commerce.CommerceError as exc:
        raise _error(exc) from None


@router.get("/v1/me/usage")
async def usage():
    try:
        return {"period": commerce.entitlement()["period"], "usage": commerce.get_usage()}
    except commerce.CommerceError as exc:
        raise _error(exc) from None


@router.get("/v1/me/grants")
async def grants():
    try:
        return {"grants": commerce.entitlement()["grants"]}
    except commerce.CommerceError as exc:
        raise _error(exc) from None


@router.post("/v1/promos/preview")
async def preview_promo(payload: PromoInput):
    try:
        return commerce.preview_promo(payload.code)
    except commerce.CommerceError as exc:
        raise _error(exc) from None


@router.post("/v1/promos/redeem")
async def redeem_promo(payload: PromoRedeem, request: Request):
    if not request.headers.get("Idempotency-Key"):
        raise HTTPException(400, {"code":"IDEMPOTENCY_REQUIRED","message":"Retry safely with an Idempotency-Key."})
    try:
        return commerce.redeem_promo(payload.code, payload.selected_plan)
    except commerce.CommerceError as exc:
        raise _error(exc) from None


@router.get("/v1/me/provider-keys")
async def provider_keys():
    return {"keys": commerce.list_provider_keys(), "preferences": commerce.provider_preferences()}


@router.post("/v1/me/provider-keys/{provider}")
async def connect_provider(provider: Literal["groq", "gemini"], payload: ProviderKey):
    try:
        return await commerce.save_provider_key(provider, payload.key)
    except commerce.CommerceError as exc:
        raise _error(exc) from None


@router.delete("/v1/me/provider-keys/{provider}", status_code=204)
async def disconnect_provider(provider: Literal["groq", "gemini"]):
    try:
        commerce.remove_provider_key(provider)
    except commerce.CommerceError as exc:
        raise _error(exc) from None


@router.put("/v1/me/provider-preferences")
async def update_preferences(payload: Preferences):
    try:
        return {"preferences": commerce.set_preferences([item.model_dump() for item in payload.preferences])}
    except commerce.CommerceError as exc:
        raise _error(exc) from None


@router.get("/v1/billing/subscription")
async def billing():
    data = commerce.entitlement()
    return {"base_plan": data["base_plan"], "effective_plan": data["effective_plan"], "payment_status":"not_configured", "payment_enabled":False, "grants":data["grants"]}


@router.post("/v1/billing/checkout")
async def checkout():
    # Payment activation is deliberately configuration-gated. A server endpoint
    # never accepts price/plan details from the browser.
    raise HTTPException(503, {"code":"PAYMENTS_NOT_CONFIGURED","message":"Online payments are not configured yet. Use a verified promo or contact MindMesh."})


@router.get("/v1/admin/promos")
async def admin_promos():
    try:
        return {"promos": commerce.list_promos()}
    except commerce.CommerceError as exc:
        raise _error(exc) from None


@router.post("/v1/admin/promos", status_code=201)
async def admin_create_promo(payload: PromoCreate):
    try:
        return commerce.create_promo(payload.model_dump())
    except commerce.CommerceError as exc:
        raise _error(exc) from None

