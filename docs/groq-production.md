# Groq production rollout

This adds Groq `openai/gpt-oss-20b` as the cloud LLM default while leaving the local Ollama model and local execution path unchanged. AWS and GCP continue to use their own existing Secret Manager wiring.

## Runtime configuration

Cloud API and worker services read `LLM_PROVIDER=groq`, `GROQ_MODEL=openai/gpt-oss-20b`, and backend-only `GROQ_API_KEY`. An optional `GROQ_API_KEY_SECONDARY` is used once only after the primary key returns a credential-specific 401. A 429 never rotates keys. Both keys must belong to authorized projects; they do not multiply organization quota.

The initial internal Redis safety ceilings are `GROQ_SAFE_RPM=24`, `GROQ_SAFE_RPD=800`, `GROQ_SAFE_TPM=6400`, and `GROQ_SAFE_TPD=160000` (defaults are 80% of the documented 30 RPM / 1,000 RPD / 8,000 TPM / 200,000 TPD snapshot). These are conservative rolling application budgets; inspect live Groq organization limits and reduce them if other apps share that organization. Redis is shared across API/worker replicas. Provider 429 responses create a shared cooldown using `Retry-After` or the relevant exhausted reset header; keys are never rotated to evade quota. Token reservations use a prompt-size estimate and are reconciled to actual usage when Groq returns token counts. A Redis circuit breaker opens after the configured consecutive upstream-failure threshold.

Groq usage headers `x-ratelimit-*-requests` are recorded as RPD and `x-ratelimit-*-tokens` as TPM. The analytics UI labels quota scope as organization/project/model; values are not represented as key-specific remaining quota. Provider event rows include token counts only when Groq returns them and never contain prompt/completion text or API secrets.

## Deploy and migrate

1. In Groq Console, confirm the production project's access to `openai/gpt-oss-20b` and review its current limits and usage policy.
2. Set the backend `GROQ_API_KEY` secret in AWS Secrets Manager or Google Secret Manager. For the optional secondary credential, set `enable_groq_secondary = true` in the chosen cloud's Terraform variables and add `GROQ_API_KEY_SECONDARY` to that platform's backend secret store before applying/redeploying. Use a distinct authorized credential for key resiliency, not quota bypass.
3. Confirm Redis is reachable by the API and worker services. This is required for shared application/provider limits in production.
4. Apply `backend/migrations/202610140003_llm_usage_analytics.sql` using the established Supabase migration process before deploying the API image.
5. Keep `MINDMESH_EXECUTION_MODE=local` for development. Cloud infrastructure sets `GROQ_MODEL` from `infra/aws` or `infra/gcp` `llm_model`; the checked-in examples now select GPT-OSS 20B.
6. Deploy API and workers together, then make one Ask AI request and process one new item. Confirm the calls appear under their respective task labels in **API Key Analytics**.
7. Verify a 401 can use the optional secondary credential, a 429 does not rotate keys, and the admin dashboard exposes no raw key or prompt text.

## Rollback and retention

To roll back the application, deploy the previous API/worker image and previous infrastructure revision. Do not drop the usage table during application rollback; the prior code ignores it. To disable Groq usage, set the cloud provider to a deliberately provisioned alternate (`xai`) or pause AI actions; removing the secret alone makes cloud startup validation fail. The migration is additive. The database comment describes the retention policy: schedule a daily deletion of rows older than `LLM_USAGE_RETENTION_DAYS` (default 90) after confirming the desired retention for your account. Do not run cleanup against an unreviewed production database.

## Limitations to monitor

- The Redis provider budgets are internal rolling windows; Groq's organization-level limits and actual response headers remain authoritative.
- The analytics dashboard shows the latest 100 individual provider attempts and 30-day task aggregates.
- Token usage remains unknown when the provider does not return usage metadata; no estimate is presented as actual usage.
- Secondary key health is inferred from a 401 event; credentials are never written to the database.

## Official Groq documentation

- [Rate limits and headers](https://console.groq.com/docs/rate-limits)
- [Projects and organization ceilings](https://console.groq.com/docs/projects)
- [GPT-OSS 20B model](https://console.groq.com/docs/model/openai/gpt-oss-20b)
- [Chat Completions API parameters](https://console.groq.com/docs/api-reference)
