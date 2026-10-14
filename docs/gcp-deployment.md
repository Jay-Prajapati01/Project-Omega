# Google Cloud production deployment

This is a **separate GCP deployment option**. Its Terraform is in `infra/gcp` and its manual GitHub Actions workflow is `.github/workflows/gcp-deploy.yml`. It does not use the AWS VPC, ECS, ALB, ElastiCache, or AWS workflow. The GCP stack uses Cloud Run for the website/API/private dispatcher, Cloud Run Jobs for processing, Cloud Tasks for dispatch, Memorystore for shared Redis limits, Secret Manager, Artifact Registry, a global HTTPS load balancer, and Cloud Armor.

The app's identity, Postgres database, private file storage, vector database, and AI providers remain external services: production Supabase, hosted Qdrant, and the configured Gemini plus Groq or xAI accounts. This guide is for an operator with project owner/IAM/network permissions and access to the GitHub repository. It does not create resources until you apply Terraform. It has recurring GCP charges, especially for the load balancer, Cloud Armor, HA Redis, VPC peering, Cloud Run minimum instances, and logging.

## Before you open the consoles

Have the following, using real production values:

- A Google account with a billing account and permission to create a dedicated production project. Do not reuse a personal sandbox project.
- A domain and DNS access for two hostnames, for example `app.example.com` and `api.example.com`.
- A production Supabase project with Auth, Postgres transaction-pooler URL, private Storage bucket, required migrations, and the correct website/callback URLs.
- Hosted Qdrant with a new collection matching the selected embedding model and dimension. Do not reuse vectors created by another embedding model.
- Gemini embedding credentials and either Groq or xAI chat credentials. Confirm current model availability and spending limits in those provider accounts.
- GitHub access to `Jay-Prajapati01/Project-Omega`, plus Docker, Google Cloud CLI, and Terraform 1.9 or later on the operator workstation.
- The real business name and monitored privacy contact email. The app's privacy text must be reviewed against actual practices before public launch.

The Terraform example uses `asia-south1`, 2 minimum API instances, 1 minimum website instance, a 1-GiB HA Redis instance, and a global load balancer. These are starting values, **not a price estimate**. Review the [Google Cloud Pricing Calculator](https://cloud.google.com/products/calculator) and set budget alerts before provisioning. Cloud Billing budget alerts notify; an alerts-only budget does not automatically stop spending. [Google Cloud budget guide](https://docs.cloud.google.com/billing/docs/how-to/budgets)

## 1. Create a dedicated project and cost alert

1. Open [Google Cloud Console](https://console.cloud.google.com/). In the project selector at the top, choose **New project**.
2. Enter a project name such as `MindMesh Production`, select your organization/location if prompted, and choose **Create**. Record the immutable **Project ID**; Terraform requires the ID, not the display name.
3. Select the new project. Open **Navigation menu → Billing**. Choose the billing account and link it to this project. If you cannot link billing, ask the billing administrator to do it before continuing.
4. Open **Navigation menu → Billing → Budgets & alerts → Create budget**. Set the scope to this project, choose a monthly budget amount you can afford, and set alert thresholds (for example 50%, 80%, and 100%). Add your monitored email and save. Review the estimate first; the budget is not a spending cap.
5. Do not create Cloud Run services by hand. Terraform owns the stack so the service ingress, identities, secrets, routing, and WAF settings stay consistent.

## 2. Prepare production data and DNS

1. In [Supabase](https://supabase.com/dashboard), create/select the production project. Open **Project Settings → API** and copy the Project URL and publishable/anon key. Keep the service-role key private.
2. Open **SQL Editor** and apply the checked-in `backend/migrations/*.sql` migrations in filename order. Stop and resolve any error; confirm the private `mindmesh-private` Storage bucket exists.
3. Open **Authentication → URL Configuration**. Set **Site URL** to `https://app.example.com` and add the exact production callback/redirect URLs used by the app. Configure provider and Auth rate limits/CAPTCHA before public signup.
4. In your Qdrant provider console, create/verify the production cluster and collection with the same dimension as `embedding_dim` below. Copy its HTTPS endpoint and private API key.
5. Create provider keys and configure their spend limits/alerts. This deployment selects Gemini for embeddings and Groq for chat by default; xAI is also supported by changing Terraform variables.
6. In your domain DNS provider, leave the two hostnames ready to add `A` records after Terraform returns its reserved global IP. Do not point live traffic at an incomplete deployment.

## 3. Create a private Terraform state bucket

1. In Google Cloud Console, open **Cloud Storage → Buckets → Create**.
2. Choose the same project, a globally unique bucket name, and a nearby region. Keep **Public access prevention** enabled, use uniform bucket-level access, and enable object versioning. Restrict bucket IAM to the deployment operators.
3. Treat Terraform state as sensitive: it contains infrastructure metadata and generated secret values. Never make the bucket public, commit state/plan files, or share state snapshots. GCS backend state locking is handled by Terraform.
4. Copy `infra/gcp/backend.gcs.tf.example` to `infra/gcp/backend.tf`; set the bucket name and an environment-specific prefix. This real file is ignored by Git.

## 4. Configure and apply the GCP foundation

Run the commands in a terminal at the repository root. On Windows PowerShell, use `Copy-Item` for the example files. Authenticate using your own operator account; GitHub deployments will use keyless Workload Identity Federation (WIF), not a downloaded service-account key.

```powershell
gcloud init
gcloud config set project YOUR_PROJECT_ID
gcloud auth application-default login
Copy-Item infra/gcp/terraform.tfvars.example infra/gcp/terraform.tfvars
```

Edit the ignored `infra/gcp/terraform.tfvars` and enter real values for `project_id`, `web_domain`, `api_domain`, and `qdrant_url`. Check `embedding_model` and `embedding_dim` against the collection. Keep `deploy_services = false` on the first pass. Do not put provider keys in this file.

Then initialize and review the foundation plan from `infra/gcp`:

```powershell
Set-Location infra/gcp
terraform init
terraform plan -out foundation.tfplan
terraform show foundation.tfplan
```

Review the plan for the correct project, region, hostnames, bucket-backed state, and expected monthly services. The first phase creates APIs, Artifact Registry, VPC/private service access, Memorystore, Secret Manager metadata and generated internal secrets, Cloud Tasks, service accounts, and GitHub WIF. It does not create public services or a load balancer. Apply only after review:

```powershell
terraform apply foundation.tfplan
terraform output
Set-Location ../..
```

If Terraform reports a billing/API/IAM permission error, fix that prerequisite and run `terraform plan` again. Do not work around an error by granting project-wide Owner to GitHub Actions.

## 5. Add the application secrets

Terraform creates Secret Manager entries for the application secrets and automatically creates the dispatch token, Redis AUTH secret, Redis TLS CA secret, and a safe `disabled` value for the optional owner bootstrap. Add versions for the application entries below. Do **not** overwrite the three generated internal secrets.

1. In Google Cloud Console, use the project selector to verify the production project.
2. Open **Security → Secret Manager**. Open each named secret, choose **Add new version**, paste the value, and choose **Add new version** again to save. Repeat for:
   - `supabase-url` ← `SUPABASE_URL` (usually safe/public but keep setup consistent)
   - `supabase-anon-key` ← `SUPABASE_ANON_KEY` (publishable/anon key)
   - `supabase-service-role-key` ← `SUPABASE_SERVICE_ROLE_KEY` (server only)
   - `supabase-db-url` ← `SUPABASE_DB_URL` (TLS transaction-pooler URL)
   - `qdrant-api-key` ← `QDRANT_API_KEY`
   - `gemini-api-key` ← `GEMINI_API_KEY`
   - `groq-api-key` ← `GROQ_API_KEY` (or supply `XAI_API_KEY` if `llm_provider = "xai"`)
   - `xai-api-key` ← `XAI_API_KEY` (leave empty only when not selected)
   - `byok-encryption-key` ← `BYOK_ENCRYPTION_KEY` (fresh base64url-encoded 32-byte value)
   - `promo-hmac-pepper` ← `PROMO_HMAC_PEPPER` (fresh long random value)
   - `owner-bootstrap-user-id` already contains `disabled`. Leave it that way unless you have created the real owner account; then add a new version containing that account's Supabase Auth UUID.
3. Use a password manager or trusted cryptographic generator for the BYOK and HMAC values. Do not reuse development secrets. Restrict Secret Manager access; the runtime service accounts receive access from Terraform.

Google Secret Manager instructions: [create and access secrets](https://docs.cloud.google.com/secret-manager/docs/creating-and-accessing-secrets).

## 6. Configure GitHub's keyless deployment identity

Terraform creates the WIF pool/provider and a deploy service account restricted to this repository's `main` branch. It does not create a service-account key.

1. Copy the Terraform outputs `workload_identity_provider`, `github_deploy_service_account`, and `artifact_registry_repository` from `terraform output`.
2. In GitHub, open the repository → **Settings → Secrets and variables → Actions → Variables → New repository variable**. Add these variables:

   | Variable | Value |
   | --- | --- |
   | `GCP_PROJECT_ID` | Project ID |
   | `GCP_REGION` | Same region as Terraform, e.g. `asia-south1` |
   | `GCP_ARTIFACT_REPOSITORY` | Terraform `artifact_registry_repository` output |
   | `GCP_WORKLOAD_IDENTITY_PROVIDER` | Terraform `workload_identity_provider` output, full resource name |
   | `GCP_DEPLOY_SERVICE_ACCOUNT` | Terraform `github_deploy_service_account` output |
   | `WEB_DOMAIN` | Website hostname only, e.g. `app.example.com` |
   | `API_DOMAIN` | API hostname only, e.g. `api.example.com` |
   | `SUPABASE_URL` | Production project URL |
   | `SUPABASE_PUBLISHABLE_KEY` | Browser-safe publishable/anon key |
   | `PRIVACY_BUSINESS_NAME` | Real business/legal identity for the public notice |
   | `PRIVACY_CONTACT_EMAIL` | Monitored public privacy contact |
   | `GA_MEASUREMENT_ID` | Optional; leave unset if analytics is not configured |

3. Do not add a Google service account JSON key. The workflow exchanges GitHub's OIDC token through WIF. Google setup reference: [Workload Identity Federation for deployment pipelines](https://docs.cloud.google.com/iam/docs/workload-identity-federation-with-deployment-pipelines) and [Google auth action](https://github.com/google-github-actions/auth).

## 7. Build images, enable services, and publish DNS

1. In GitHub, open **Actions → Build and deploy MindMesh to Google Cloud → Run workflow**. Select `main`; leave `deploy` unchecked for this first run. This builds API, worker, and website images and pushes both `prod` and commit-SHA tags to Artifact Registry.
2. Confirm the run succeeded and the three image repositories contain the new SHA tag. If it fails, open the failed step and fix missing repository variables, WIF conditions, project permissions, or a Docker build error before continuing.
3. In `infra/gcp/terraform.tfvars`, change `deploy_services = true`. Then plan, inspect, and apply the public service phase:

   ```powershell
   Set-Location infra/gcp
   terraform plan -out services.tfplan
   terraform show services.tfplan
   terraform apply services.tfplan
   terraform output
   Set-Location ../..
   ```

   This creates the web/API Cloud Run services, private dispatcher, Cloud Run worker Job, serverless NEGs, Cloud Armor policy, global external HTTPS load balancer, reserved static IP, HTTP-to-HTTPS redirect, and Google-managed certificate. Services accept public traffic through the load balancer; the dispatcher is internal-only. [Cloud Run ingress guidance](https://docs.cloud.google.com/run/docs/securing/ingress) · [Cloud Armor with serverless backends](https://docs.cloud.google.com/armor/docs/security-policy-overview).

Cloud Tasks invokes the dispatcher using an OIDC token with the dispatcher service URL as its audience; the API can enqueue tasks, and the dispatcher runtime identity receives the permission to execute the worker Job with its required job-ID override. See [Cloud Tasks authenticated HTTP targets](https://docs.cloud.google.com/tasks/docs/creating-http-target-tasks) and [Cloud Run IAM roles](https://docs.cloud.google.com/iam/docs/roles-permissions/run).

4. Copy `load_balancer_ip` from Terraform output. In your DNS provider, create `A` records for both hostnames pointing at that IP. Do not create a CNAME at the zone apex unless your DNS provider explicitly supports alias/flattening records.
5. In Google Cloud Console, open **Network services → Load balancing** and check the MindMesh load balancer, frontend IP, backends, and certificate status. The managed certificate becomes active only after DNS points to the correct IP and certificate provisioning finishes. Keep the default Cloud Run URLs inaccessible from the public internet via the configured ingress. Google recommends an external Application Load Balancer for serverless custom domains; Cloud Run domain mapping is not the production path here. [Serverless load balancer guide](https://docs.cloud.google.com/load-balancing/docs/https/setting-up-https-serverless).

6. In Supabase **Authentication → URL Configuration**, double-check the live website URL and redirect allowlist. The application uses a Google global load balancer, and the API selects the client IP added to `X-Forwarded-For` by that proxy for IP fallback limits.

## 8. Release future changes

1. Merge the reviewed change to `main`.
2. Open GitHub **Actions → Build and deploy MindMesh to Google Cloud → Run workflow**.
3. For a build-only release, leave `deploy` unchecked. To roll out the just-built commit to Cloud Run services and the worker Job, check `deploy` and run the workflow.
4. The workflow deploys immutable SHA images to `mindmesh-api`, `mindmesh-web`, `mindmesh-dispatcher`, and `mindmesh-worker`. Keep the previous SHA available for rollback. If you later change Terraform-managed service settings, apply Terraform as well; workflow rollout changes only the images.

## 9. Verify launch health and keep watch

Before deploying the Groq usage dashboard, apply `backend/migrations/202610140003_llm_usage_analytics.sql` to the configured Supabase/Postgres database. Set `GROQ_API_KEY` (and optional `GROQ_API_KEY_SECONDARY`) as backend Google Secret Manager values. Terraform examples select `openai/gpt-oss-20b`; confirm live Groq limits and the shared Memorystore budgets first. See [Groq production rollout](groq-production.md) for end-to-end verification and rollback steps.

1. Open `https://app.example.com` and `https://api.example.com/api/health/detailed`; verify HTTPS, API/database/Redis readiness, login and password recovery, account isolation, uploads, YouTube/Instagram processing, AI chat, job status, contact form, analytics consent, privacy notice, and 404 page.
2. Open **Cloud Run → Services**; inspect `mindmesh-api`, `mindmesh-web`, and `mindmesh-dispatcher` for healthy revisions and errors. Open **Cloud Run → Jobs → mindmesh-worker → Executions** to inspect completed/failed processing jobs.
3. Open **Logging → Logs Explorer** and filter by the Cloud Run service name. New Google Cloud projects route application and service logs to the `_Default` bucket, which retains logs for 30 days unless you change it. Check application and load-balancer logs, 429/503 counts, failed job retries, database pool errors, and provider errors. Keep retention aligned with your actual privacy policy. [Cloud Logging storage defaults](https://docs.cloud.google.com/logging/docs/store-log-entries).
4. Open **Cloud Tasks → Queues → mindmesh-jobs** and check queue depth, retries, and dispatch failures. Open **Memorystore for Redis → mindmesh-production-redis** and confirm the instance is healthy. Redis TLS uses port 6378 and its CA is mounted to each backend runtime. [Memorystore TLS instructions](https://docs.cloud.google.com/memorystore/docs/redis/manage-in-transit-encryption).
5. In **Monitoring → Uptime checks**, add an HTTPS check for the public website and API health URL. Add alerting for availability, 5xx responses, Cloud Run instance failures, Cloud Tasks backlog, database/Redis reachability, and budget thresholds; route alerts to an inbox someone monitors.
6. Run the load scenario only against isolated staging with representative account data and non-production provider credentials. The existing scenario does not exercise expensive ingestion or paid AI calls.

## Known launch limits and rollback

- Cloud Run's HTTP/1 request size limit is 32 MiB. This configuration caps multipart bodies at 30 MiB and files at 28 MiB. Larger user files need a later direct-to-private-Storage signed-upload flow. [Cloud Run quotas](https://docs.cloud.google.com/run/quotas).
- Source, note, conversation, and graph state still relies on the legacy `mm_state` JSON document. The normalized-table migration has not switched application reads/writes or backfilled data, so do not infer large-tenant scale from its indexes.
- A Cloud Run Job is launched per dispatched job; the configured Cloud Tasks rate/concurrency are conservative starting values, not a measured capacity guarantee. Increase only after staging load tests and checking provider, database, Redis, and Cloud Run quotas.
- Payments remain disabled. Do not advertise paid plans until billing credentials, webhook signatures, and end-to-end flows are configured and verified.
- Public privacy and FAQ content needs real business/contact details and legal review. The app must not launch with invented placeholder details.
- To roll back, run the GCP workflow against a previous commit SHA after adjusting its image tag logic, or use Cloud Run revision traffic controls for a previous revision. Then inspect Cloud Run, Cloud Tasks, load balancer, and logs before restoring traffic.
- No GCP resources are provisioned by this repository change. Do not apply the Terraform plan until its project, secrets, domains, cost, and service settings are reviewed.
