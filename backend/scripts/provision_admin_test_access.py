"""Provision the first MindMesh administrator and initial test promos.

This script is intentionally local-only. It creates the requested Supabase
Auth user, gives that user an administrative role in the commerce schema, and
writes the password and generated promo codes to an ignored Markdown file.

Run only after the commerce migration has been applied::

    python scripts/apply_supabase_migrations.py
    python scripts/provision_admin_test_access.py

It requires SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY and a working
SUPABASE_DB_URL in backend/.env. No credential or raw promo code is stored in
source control or in the database; the database stores an HMAC of each code.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sys
from pathlib import Path

import httpx
import psycopg


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
ENV_FILE = BACKEND / ".env"
OUTPUT = ROOT / "admin-portal-test-credentials.md"
ADMIN_EMAIL = "admin@mindmesh.com"
ADMIN_PASSWORD = "admin@theRate1234"


def load_environment() -> dict[str, str]:
    values = dict(os.environ)
    if ENV_FILE.exists():
        for raw in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    return values


def require(values: dict[str, str], key: str) -> str:
    value = values.get(key, "").strip()
    if not value:
        raise RuntimeError(f"{key} is missing from backend/.env")
    return value


def ensure_pepper(values: dict[str, str]) -> str:
    pepper = values.get("PROMO_HMAC_PEPPER", "").strip()
    if pepper:
        return pepper
    pepper = secrets.token_urlsafe(48)
    suffix = "" if not ENV_FILE.exists() or ENV_FILE.read_text(encoding="utf-8").endswith("\n") else "\n"
    with ENV_FILE.open("a", encoding="utf-8") as stream:
        stream.write(f"{suffix}PROMO_HMAC_PEPPER={pepper}\n")
    values["PROMO_HMAC_PEPPER"] = pepper
    return pepper


def hmac_code(code: str, pepper: str) -> str:
    return hmac.new(pepper.encode(), code.upper().encode(), hashlib.sha256).hexdigest()


def random_code(label: str) -> str:
    return f"MM-{label}-{secrets.token_urlsafe(12).upper().replace('-', '').replace('_', '')}"


def auth_user_id(conn: psycopg.Connection, base_url: str, service_key: str) -> str:
    existing = conn.execute("select id::text from auth.users where lower(email)=lower(%s)", (ADMIN_EMAIL,)).fetchone()
    headers = {"apikey": service_key, "Authorization": f"Bearer {service_key}", "Content-Type": "application/json"}
    if existing:
        response = httpx.put(f"{base_url.rstrip('/')}/auth/v1/admin/users/{existing[0]}", headers=headers, json={"password": ADMIN_PASSWORD, "email_confirm": True}, timeout=20)
        response.raise_for_status()
        return existing[0]
    response = httpx.post(f"{base_url.rstrip('/')}/auth/v1/admin/users", headers=headers, json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD, "email_confirm": True}, timeout=20)
    response.raise_for_status()
    user_id = response.json().get("id")
    if not user_id:
        raise RuntimeError("Supabase did not return the new administrator user id")
    return str(user_id)


def table_exists(conn: psycopg.Connection, table: str) -> bool:
    return conn.execute("select to_regclass(%s)", (f"public.{table}",)).fetchone()[0] is not None


def add_promo(conn: psycopg.Connection, code: str, pepper: str, *, campaign: str, kind: str, hours: int, cap: int, created_by: str) -> None:
    conn.execute(
        """insert into public.mm_promo_codes
           (code_hmac,preview_prefix,campaign_name,description,kind,allowed_plans,duration_hours,max_total_redemptions,max_per_user,created_by)
           values(%s,%s,%s,%s,%s,array['pro'],%s,%s,1,%s)""",
        (hmac_code(code, pepper), code[:6] + "…", campaign,
         "Provisioned by the local administrator setup script.", kind, hours, cap, created_by),
    )


def write_credentials(*, role: str, admin_code: str, beta_code: str) -> None:
    OUTPUT.write_text(
        f"""# MindMesh administrator test access

Generated locally by `backend/scripts/provision_admin_test_access.py`.
This file is ignored by Git because it contains credentials and raw promo codes.

## Administrator portal

- Email: `{ADMIN_EMAIL}`
- Password: `{ADMIN_PASSWORD}`
- Assigned role: `{role}`
- Portal: `/admin/promo-codes`

Use this account to sign in first, then open the portal. The role is assigned
in Supabase and is not granted by any promo code.

## Initial promo campaigns

| Audience | Code | Access | Redemption limit |
| --- | --- | --- | --- |
| Founder administrator | `{admin_code}` | Pro plan for 365 days | 1 account |
| Beta testers | `{beta_code}` | Pro plan for 30 days | 100 accounts |

Promo codes grant only the displayed temporary plan access. They never grant
administrator rights. Create, pause, or revoke later campaigns from the admin
portal after signing in with the administrator account.
""",
        encoding="utf-8",
    )


def main() -> int:
    values = load_environment()
    db_url = require(values, "SUPABASE_DB_URL")
    base_url = require(values, "SUPABASE_URL")
    service_key = require(values, "SUPABASE_SERVICE_ROLE_KEY")
    pepper = ensure_pepper(values)
    with psycopg.connect(db_url, connect_timeout=15) as conn:
        missing = [name for name in ("mm_profiles", "mm_user_roles", "mm_subscriptions", "mm_promo_codes") if not table_exists(conn, name)]
        if missing:
            raise RuntimeError("Commerce migration is not applied. Missing tables: " + ", ".join(missing))
        admin_id = auth_user_id(conn, base_url, service_key)
        conn.execute("insert into public.mm_profiles(user_id) values(%s) on conflict(user_id) do nothing", (admin_id,))
        conn.execute("insert into public.mm_subscriptions(user_id,base_plan) values(%s,'pro') on conflict(user_id) do update set base_plan='pro', updated_at=now()", (admin_id,))
        owner_exists = conn.execute("select 1 from public.mm_user_roles where role='owner' and revoked_at is null").fetchone() is not None
        role = "admin" if owner_exists else "owner"
        conn.execute("insert into public.mm_user_roles(user_id,role,granted_by) values(%s,%s,%s) on conflict(user_id,role) do update set revoked_at=null", (admin_id, role, admin_id))
        admin_code, beta_code = random_code("FOUNDER"), random_code("BETA")
        add_promo(conn, admin_code, pepper, campaign="Founder Pro access", kind="plan_grant", hours=8760, cap=1, created_by=admin_id)
        add_promo(conn, beta_code, pepper, campaign="Beta tester Pro access", kind="beta_grant", hours=720, cap=100, created_by=admin_id)
        conn.commit()
    write_credentials(role=role, admin_code=admin_code, beta_code=beta_code)
    print(f"Provisioned administrator and promo campaigns. Read {OUTPUT}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, httpx.HTTPError, psycopg.Error) as error:
        print(f"Provisioning stopped: {error}", file=sys.stderr)
        raise SystemExit(1)
