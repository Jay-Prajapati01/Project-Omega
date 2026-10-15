# Groq production rollout

This adds Groq `openai/gpt-oss-20b` as the cloud LLM default while leaving the local Ollama model and local execution path unchanged. AWS and GCP continue to use their own existing Secret Manager wiring.

## Runtime configuration

Cloud API and worker services read `LLM_PROVIDER=groq`, `GROQ_MODEL=openai/gpt-oss-20b`, and backend-only `GROQ_API_KEY`. Optional additional credentials can be supplied as comma-separated or newline-separated strings in `GROQ_API_KEYS` (or through the legacy optional `GROQ_API_KEY_SECONDARY` field). The service advances to another credential only after an authentication-specific 401. It does not rotate on 429s, provider outages, or shared cooldowns. Groq applies organization limits and may impose lower project/model limits; response headers are shared-scope observations, not per-key balances ([rate-limit docs](https://console.groq.com/docs/rate-limits), [project docs](https://console.groq.com/docs/projects)).

There is no xAI fallback in this deployment path. A Groq 429, outage, or shared circuit/cooldown produces a temporary-unavailable response; the application respects the provider's shared limits rather than switching accounts to evade them. If a separate provider is intentionally configured as the primary, its key is used only for that configured primary.

The initial internal Redis safety ceilings are `GROQ_SAFE_RPM=24`, `GROQ_SAFE_RPD=800`, `GROQ_SAFE_TPM=6400`, and `GROQ_SAFE_TPD=160000` (defaults are 80% of the documented 30 RPM / 1,000 RPD / 8,000 TPM / 200,000 TPD snapshot). These are conservative rolling application budgets; inspect live Groq organization limits and reduce them if other apps share that organization. Redis is shared across API/worker replicas. Provider 429 responses create a shared cooldown using `Retry-After` or the relevant exhausted reset header; keys are never rotated to evade quota. Token reservations use a prompt-size estimate and are reconciled to actual usage when Groq returns token counts. A Redis circuit breaker opens after the configured consecutive upstream-failure threshold.

Groq usage headers `x-ratelimit-*-requests` are recorded as RPD and `x-ratelimit-*-tokens` as TPM. Analytics shows per-alias requests, outcomes, and observed tokens as activity attribution, not a per-key quota. The latest provider headers are shown at their shared scope. Provider event rows include token counts only when a provider returns them and never contain prompt/completion text or API secrets.

## Deploy and migrate

1. In Groq Console, confirm the production project's access to `openai/gpt-oss-20b` and review its current limits and usage policy.
2. Set the backend `GROQ_API_KEY` secret in AWS Secrets Manager or Google Secret Manager. Additional authorized credentials may be placed one per line or comma-separated in `GROQ_API_KEYS`; the legacy `GROQ_API_KEY_SECONDARY` field is also supported. These credentials only provide recovery from a rejected/invalid key (401), not quota failover. Do not use multiple accounts to circumvent provider limits or free-tier restrictions.
3. Confirm Redis is reachable by the API and worker services. This is required for shared application/provider limits in production.
4. Apply `backend/migrations/202610140003_llm_usage_analytics.sql` using the established Supabase migration process before deploying the API image.
5. Keep `MINDMESH_EXECUTION_MODE=local` for development. Cloud infrastructure sets `GROQ_MODEL` from `infra/aws` or `infra/gcp` `llm_model`; the checked-in examples now select GPT-OSS 20B.
6. Deploy API and workers together, then make one Ask AI request and process one new item. Confirm the calls appear under their respective task labels in **API Key Analytics**.
7. Verify a 401 can use the next configured credential, a 429 does not rotate credentials, and the admin dashboard exposes no raw key or prompt text.

## Rollback and retention

To roll back the application, deploy the previous API/worker image and previous infrastructure revision. Do not drop the usage table during application rollback; the prior code ignores it. To disable Groq usage, set the cloud provider to a deliberately provisioned alternate (`xai`) or pause AI actions; removing the secret alone makes cloud startup validation fail. The migration is additive. The database comment describes the retention policy: schedule a daily deletion of rows older than `LLM_USAGE_RETENTION_DAYS` (default 90) after confirming the desired retention for your account. Do not run cleanup against an unreviewed production database.

## Limitations to monitor

- The Redis provider budgets are internal rolling windows; they are not authoritative provider quota. Groq does not report a separate remaining-quota balance per API key.
- The analytics dashboard shows the latest 100 individual provider attempts and 30-day task aggregates.
- Token usage remains unknown when the provider does not return usage metadata; no estimate is presented as actual usage.
- Secondary key health is inferred from a 401 event; credentials are never written to the database.

## Official Groq documentation

- [Rate limits and headers](https://console.groq.com/docs/rate-limits)
- [Projects and organization ceilings](https://console.groq.com/docs/projects)
- [GPT-OSS 20B model](https://console.groq.com/docs/model/openai/gpt-oss-20b)
- [Chat Completions API parameters](https://console.groq.com/docs/api-reference)
