"""Delete expired staging objects and age out terminal job results."""
import httpx
from app.core.config import get_settings
from app.services.cloud_db import connect


def cleanup_staging() -> int:
    cfg = get_settings()
    # Grace period exceeds job TTL and hard worker timeout, including retries.
    with connect() as conn:
        rows = conn.execute("""SELECT name FROM storage.objects WHERE bucket_id=%s
            AND split_part(name,'/',2) IN ('inputs','scratch')
            AND updated_at < now() - interval '8 days' LIMIT 500""",
            (cfg.supabase_storage_bucket,)).fetchall()
    names = [row[0] for row in rows]
    if names:
        with httpx.Client(timeout=60) as client:
            response = client.request("DELETE", f"{cfg.supabase_url}/storage/v1/object/{cfg.supabase_storage_bucket}",
                headers={"Authorization": f"Bearer {cfg.supabase_service_role_key}"}, json={"prefixes": names})
            response.raise_for_status()
    return len(names)


def purge_expired_job_results() -> int:
    """Retention for mirrored terminal job results (audit P1-8)."""
    cfg = get_settings()
    with connect() as conn:
        result = conn.execute(
            "DELETE FROM public.mm_job_results WHERE created_at < now() - make_interval(days => %s)",
            (cfg.job_result_retention_days,))
        return result.rowcount or 0


def maintenance() -> dict:
    """Daily maintenance sweep: staged objects + job-result retention."""
    return {"staging_deleted": cleanup_staging(),
            "job_results_purged": purge_expired_job_results()}
