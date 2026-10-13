"""Provision the first MindMesh administrator and initial test promos.

This script is an explicit, local operator tool. Set OWNER_EMAIL to an address
you control. A new account receives a generated one-time password; an existing
account is never reset. Generated credentials are written to an ignored file.

Run only after the commerce migration has been applied::

    python scripts/apply_supabase_migrations.py
    python scripts/provision_admin_test_access.py

It requires OWNER_EMAIL, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY and a working
SUPABASE_DB_URL. Set CREATE_INITIAL_PROMOS=true only when you intentionally
want the two sample launch campaigns. This script is not part of AWS startup.
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


def auth_user_id(conn: psycopg.Connection, base_url: str, service_key: str, email: str) -> tuple[str, str | None]:
    existing = conn.execute("select id::text from auth.users where lower(email)=lower(%s)", (email,)).fetchone()
    if existing:
        return existing[0], None
    initial_password = secrets.token_urlsafe(32)
    headers = {"apikey": service_key, "Authorization": f"Bearer {service_key}", "Content-Type": "application/json"}
    response = httpx.post(f"{base_url.rstrip('/')}/auth/v1/admin/users", headers=headers, json={"email": email, "password": initial_password, "email_confirm": True}, timeout=20)
    response.raise_for_status()
    user_id = response.json().get("id")
    if not user_id:
        raise RuntimeError("Supabase did not return the new administrator user id")
    return str(user_id), initial_password


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


def write_credentials(*, email: str, initial_password: str | None, role: str, admin_code: str | None, beta_code: str | None) -> None:
    password_note = (
        f"- Initial password: `{initial_password}` (change it after first sign-in)"
        if initial_password
        else "- This account already existed; its password was not changed or recorded."
    )
    promo_section = (
        f"""## Initial promo campaigns

| Audience | Code | Access | Redemption limit |
| --- | --- | --- | --- |
| Founder administrator | `{admin_code}` | Pro plan for 365 days | 1 account |
| Beta testers | `{beta_code}` | Pro plan for 30 days | 100 accounts |

Promo codes grant only temporary plan access; they never grant administrator rights.
"""
        if admin_code and beta_code
        else "No promo codes were created."
    )
    OUTPUT.write_text(
        f"""# MindMesh administrator test access

Generated locally by `backend/scripts/provision_admin_test_access.py`.
This file is ignored by Git because it contains credentials and raw promo codes.

## Administrator portal

- Email: `{email}`
{password_note}
- Assigned role: `{role}`
- Portal: `/admin/promo-codes`

Use this account to sign in, then open the portal. The role is assigned in
Supabase and is not granted by any promo code.

{promo_section}
""",
        encoding="utf-8",
    )


def main() -> int:
    values = load_environment()
    db_url = require(values, "SUPABASE_DB_URL")
    base_url = require(values, "SUPABASE_URL")
    service_key = require(values, "SUPABASE_SERVICE_ROLE_KEY")
    admin_email = require(values, "OWNER_EMAIL")
    create_promos = values.get("CREATE_INITIAL_PROMOS", "false").strip().lower() == "true"
    pepper = ensure_pepper(values) if create_promos else ""
    with psycopg.connect(db_url, connect_timeout=15) as conn:
        needed_tables = ["mm_profiles", "mm_user_roles", "mm_subscriptions"]
        if create_promos:
            needed_tables.append("mm_promo_codes")
        missing = [name for name in needed_tables if not table_exists(conn, name)]
        if missing:
            raise RuntimeError("Commerce migration is not applied. Missing tables: " + ", ".join(missing))
        admin_id, initial_password = auth_user_id(conn, base_url, service_key, admin_email)
        conn.execute("insert into public.mm_profiles(user_id) values(%s) on conflict(user_id) do nothing", (admin_id,))
        conn.execute("insert into public.mm_subscriptions(user_id,base_plan) values(%s,'pro') on conflict(user_id) do update set base_plan='pro', updated_at=now()", (admin_id,))
        owner_exists = conn.execute("select 1 from public.mm_user_roles where role='owner' and revoked_at is null").fetchone() is not None
        role = "admin" if owner_exists else "owner"
        conn.execute("insert into public.mm_user_roles(user_id,role,granted_by) values(%s,%s,%s) on conflict(user_id,role) do update set revoked_at=null", (admin_id, role, admin_id))
        admin_code = beta_code = None
        if create_promos:
            admin_code, beta_code = random_code("FOUNDER"), random_code("BETA")
            add_promo(conn, admin_code, pepper, campaign="Founder Pro access", kind="plan_grant", hours=8760, cap=1, created_by=admin_id)
            add_promo(conn, beta_code, pepper, campaign="Beta tester Pro access", kind="beta_grant", hours=720, cap=100, created_by=admin_id)
        conn.commit()
    write_credentials(email=admin_email, initial_password=initial_password, role=role, admin_code=admin_code, beta_code=beta_code)
    print(f"Provisioned administrator and promo campaigns. Read {OUTPUT}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, httpx.HTTPError, psycopg.Error) as error:
        print(f"Provisioning stopped: {error}", file=sys.stderr)
        raise SystemExit(1)
