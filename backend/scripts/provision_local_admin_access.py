"""Create local Docker administrator access and the initial promo campaigns.

This is for the current localhost setup. Production provisioning remains in
``provision_admin_test_access.py`` and requires the Supabase commerce schema.
Run this inside the backend container so the shared local promo store lands in
the Docker volume, not in a transient host folder.
"""
from __future__ import annotations

import os
import secrets
from pathlib import Path

import httpx

from app.core.config import get_settings
from app.core.tenant import Scope, current_scope
from app.services import commerce

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"
# The script runs inside Docker, where /app is the backend bind mount. The
# caller copies this ignored handoff file to the repository root afterwards.
OUTPUT = ROOT / "admin-portal-test-credentials.md"
EMAIL = "admin@mindmesh.com"
PASSWORD = "admin@theRate1234"


def env_value(name: str) -> str:
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith(name + "="):
            return line.split("=", 1)[1].strip()
    return os.environ.get(name, "")


def set_env(name: str, value: str) -> None:
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines()
    replacement = f"{name}={value}"
    for index, line in enumerate(lines):
        if line.strip().startswith(name + "="):
            lines[index] = replacement
            break
    else:
        lines.append(replacement)
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def auth_user_id(url: str, key: str) -> str:
    headers = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    response = httpx.post(f"{url.rstrip('/')}/auth/v1/admin/users", headers=headers,
                          json={"email": EMAIL, "password": PASSWORD, "email_confirm": True}, timeout=20)
    if response.is_success:
        return str(response.json()["id"])
    users = httpx.get(f"{url.rstrip('/')}/auth/v1/admin/users?page=1&per_page=1000", headers=headers, timeout=20)
    users.raise_for_status()
    for user in users.json().get("users", []):
        if user.get("email", "").lower() == EMAIL:
            user_id = str(user["id"])
            update = httpx.put(f"{url.rstrip('/')}/auth/v1/admin/users/{user_id}", headers=headers,
                               json={"password": PASSWORD, "email_confirm": True}, timeout=20)
            update.raise_for_status()
            return user_id
    response.raise_for_status()
    raise RuntimeError("Could not create or locate the administrator account")


def code(label: str) -> str:
    return f"MM-{label}-{secrets.token_urlsafe(12).upper().replace('_', '').replace('-', '')}"


def main() -> None:
    url, key = env_value("SUPABASE_URL"), env_value("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key: raise RuntimeError("Supabase URL and service role key are required")
    user_id = auth_user_id(url, key)
    set_env("OWNER_BOOTSTRAP_USER_ID", user_id)
    if not env_value("PROMO_HMAC_PEPPER"):
        set_env("PROMO_HMAC_PEPPER", secrets.token_urlsafe(48))
    get_settings.cache_clear()
    token = current_scope.set(Scope(tenant_id=user_id, user_id=user_id))
    try:
        commerce.bootstrap_account()
        founder = commerce.create_promo({"code": code("FOUNDER"), "campaign_name": "Founder Pro access", "kind": "plan_grant", "allowed_plans": ["pro"], "duration_hours": 8760, "max_total_redemptions": 1})
        beta = commerce.create_promo({"code": code("BETA"), "campaign_name": "Beta tester Pro access", "kind": "beta_grant", "allowed_plans": ["pro"], "duration_hours": 720, "max_total_redemptions": 100})
    finally:
        current_scope.reset(token)
    OUTPUT.write_text(f"""# MindMesh administrator test access

## Administrator portal

- Email: `{EMAIL}`
- Password: `{PASSWORD}`
- Portal: `/admin/promo-codes`

## Initial promo campaigns

| Audience | Code | Access | Limit |
| --- | --- | --- | --- |
| Founder administrator | `{founder['code']}` | Pro plan for 365 days | 1 redemption |
| Beta testers | `{beta['code']}` | Pro plan for 30 days | 100 redemptions |

Promo codes grant plan access only. Administrator rights are attached directly
to the signed-in administrator account.
""", encoding="utf-8")
    print("Local administrator and promo campaigns provisioned.")


if __name__ == "__main__":
    main()
