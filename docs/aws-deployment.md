# AWS production deployment

This repo now includes a Terraform deployment for **ECS Fargate + Application Load Balancer + AWS WAF + ElastiCache Redis**. Supabase remains the application's Auth/Postgres/private-object-storage provider; Qdrant Cloud stores vectors; Groq or xAI supplies chat; Gemini supplies embeddings. The app's cloud worker polls the shared Postgres job table, so the AWS path uses `JOB_BACKEND=postgres` and does not depend on the existing Google Cloud Tasks adapter.

This provisions infrastructure only after an operator runs Terraform with AWS credentials. It does not create Supabase/Qdrant/provider accounts, domain ownership, or legal business details.

AWS and GCP remain separate options: this guide covers only the AWS files under `infra/aws` and the workflow `.github/workflows/aws-deploy.yml`. Do not run the GCP guide's Terraform or workflow for an AWS release.

## Before starting

Have these ready:

- An AWS account with billing alerts, an AWS region, and permission to create VPC, NAT, ECS, ECR, ALB, WAF, ElastiCache, Secrets Manager, CloudWatch, IAM, and SNS resources.
- A domain with DNS control. Create an ACM certificate in the same AWS region as the ALB, covering both `app.your-domain` and `api.your-domain`; validate it before Terraform apply.
- A **new production Supabase project**, a hosted Qdrant cluster, and provider keys for the configured LLM and Gemini embeddings.
- The real legal business name and monitored privacy contact email. The public privacy page is still a draft and must be reviewed for your actual data, retention, provider locations, and legal requirements.
- Docker, Terraform 1.9+, AWS CLI, and access to the GitHub repository.

The infrastructure uses two NAT gateways, a two-node Redis replication group, one API task, and one website task by default (optimized to stay within the 8 vCPU Fargate quota). These resources have ongoing charges. Review the AWS Pricing Calculator and your database/provider quotas before applying. Tune `api_max_count`, `web_max_count`, task sizes, and database pool sizes to the Supabase plan; the API/worker pools are per process, and each worker task has a polling process plus a job child process.

## Console setup: click-by-click

1. Sign in to the [AWS Management Console](https://console.aws.amazon.com/), choose the intended production account, then use the region selector at the top right to choose the same region you will use in Terraform (the example is `Asia Pacific (Mumbai) ap-south-1`).
2. Open **Billing and Cost Management → Budgets → Create budget → Use a template (simplified) → Monthly cost budget**. Enter a limit you can afford, add your email, and choose **Create budget**. This is an alert, not an automatic shutdown. See [AWS budget templates](https://docs.aws.amazon.com/cost-management/latest/userguide/budget-templates.html).
3. Open **Certificate Manager (ACM) → Request** (public certificate). Add both hostnames, choose DNS validation, request the certificate, and create/allow the DNS validation records. Wait until its status is **Issued** and copy its ARN. The ALB certificate must be in the ALB's region. See [ACM DNS validation](https://docs.aws.amazon.com/acm/latest/userguide/dns-validation.html).
4. Open **IAM → Identity providers**. Add an OpenID Connect provider only if `token.actions.githubusercontent.com` is not already present. Audience must be `sts.amazonaws.com`. Then open **IAM → Roles → Create role → Web identity**, choose that provider, and create a role restricted to `repo:Jay-Prajapati01/Project-Omega:ref:refs/heads/main`. Use `infra/aws/github-deploy-role-trust.example.json` and `github-deploy-role-policy.example.json` as templates; substitute your account and region and review the permissions before creating the role. Copy the role ARN. Do not create access keys for GitHub Actions.
5. Open **Route 53 → Hosted zones → your domain** only if Route 53 hosts your DNS. The application `A` records are created after Terraform returns the ALB name; ACM validation records can be created now. If a different DNS provider hosts the zone, perform the equivalent record steps there. See [Route 53 record creation](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/resource-record-sets-creating.html).
6. In **GitHub → repository → Settings → Secrets and variables → Actions**, create secret `AWS_DEPLOY_ROLE_ARN`, then repository variables `AWS_REGION`, `WEB_DOMAIN`, `API_URL`, `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, `PRIVACY_BUSINESS_NAME`, and `PRIVACY_CONTACT_EMAIL`. `API_URL` includes `/api`, for example `https://api.example.com/api`. Add `GA_MEASUREMENT_ID` only if you configure GA4.

The console paths above are setup/inspection only. Terraform creates the AWS application stack so the VPC, security groups, load balancer, WAF, ECS services, and Redis configuration stay coordinated.

## 1. Prepare the external services

1. Create a dedicated production Supabase project; don't point production at the development project's local/test data.
2. Apply every `backend/migrations/*.sql` file in filename order using the Supabase SQL editor, stopping on any SQL error. Confirm the private `mindmesh-private` Storage bucket exists and remains private.
3. In Supabase Auth, set the site URL to `https://app.your-domain` and allow the exact production callback URLs used by Supabase JS, including `https://app.your-domain/**`. Enable only the providers you plan to support.
4. Create the hosted Qdrant collection configured in `terraform.tfvars` for the chosen embedding model and dimension. A new Gemini embedding space must not reuse the local Ollama vectors. Ensure Qdrant access is HTTPS and keep its API key private.
5. Create the provider keys. Terraform defaults to Groq for LLM and Gemini embeddings; choose a current model supported by your provider account before launch.
6. If migrating existing local content, plan and verify a separate migration for Supabase state, uploaded objects, and Qdrant vectors. The local `backend/data` directory is ignored and is not copied into AWS.

## 2. Prepare state and AWS access

1. Create a private S3 bucket for Terraform state with versioning and public access blocked, plus a DynamoDB table with partition key `LockID` (string) for state locking.
2. Copy `infra/aws/backend.s3.tf.example` to `infra/aws/backend.tf`, replace the bucket/table/region values, and keep `backend.tf` out of public examples if it reveals account infrastructure identifiers.
3. Create an ACM certificate in the target region and complete DNS validation.
4. Create a GitHub Actions OIDC provider for `https://token.actions.githubusercontent.com` if the AWS account does not already have one. Create a deploy role whose trust is restricted to repository `Jay-Prajapati01/Project-Omega` and branch `main`. The trust and permissions templates are in `infra/aws/github-deploy-role-*.example.json`; replace account/region IDs before use. Grant it only ECR push access for the three MindMesh repositories and ECS `UpdateService` on the MindMesh production services. Do not use long-lived AWS access keys in GitHub.
5. In GitHub repository **Settings → Secrets and variables → Actions**, add secret `AWS_DEPLOY_ROLE_ARN` and variables `AWS_REGION`, `WEB_DOMAIN`, `API_URL`, `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, `PRIVACY_BUSINESS_NAME`, and `PRIVACY_CONTACT_EMAIL`. `API_URL` must be `https://api.your-domain/api`. Add `GA_MEASUREMENT_ID` only if GA4 is configured.

For a new state bucket, use **S3 → Create bucket**; keep **Block all public access** on, enable bucket versioning, and enable default encryption. For locking, use **DynamoDB → Tables → Create table**, table name from `backend.s3.tf.example`, partition key `LockID` with type **String**. Restrict access to the operators. Terraform state may contain secret values. For S3 backend setup, see the [Terraform AWS S3 backend guide](https://developer.hashicorp.com/terraform/language/backend/s3).

## 3. Configure Terraform and create the base infrastructure

1. Copy `infra/aws/terraform.tfvars.example` to `infra/aws/terraform.tfvars` and enter your real domains, ACM ARN, region, and Qdrant URL. Keep `deploy_services = false` for the first apply. The example hostnames and ARN are not usable values.
2. From the repository root, initialize and review a saved plan before applying. Check that it contains only the intended new production resources and inspect the estimated recurring charges in AWS Pricing Calculator.

   ```powershell
   Set-Location infra/aws
   terraform init
   terraform plan -out base.tfplan
   terraform show base.tfplan
   terraform apply base.tfplan
   terraform output
   Set-Location ../..
   ```

3. It creates the VPC/private app subnets/NAT, ALB/HTTPS/WAF, ECR repositories, ECS task definitions and cluster, ElastiCache, log groups, alarm topic, and a Secrets Manager secret. ECS services remain disabled until the images and runtime secret are ready.
4. Create Route 53 alias records for both hostnames pointing to the output ALB DNS name. If your DNS is elsewhere, create equivalent ALIAS/CNAME records there.

In Route 53, open **Hosted zones → your domain → Create record**. For each hostname, set **Record type A**, turn **Alias** on, choose **Alias to Application and Classic Load Balancer**, select the ALB's region and Terraform output load balancer, and save. At another DNS provider, create the equivalent apex-compatible alias or CNAME records. Do not publish the site until DNS and the certificate both resolve successfully.

## 4. Populate runtime secrets

In AWS Console, open **Secrets Manager → Secrets → the Terraform output secret → Retrieve secret value → Edit**. Choose the plain-text/JSON editor, paste the complete JSON object below, save, and verify it appears as the current version. Keep values in Secrets Manager; do not put them in `terraform.tfvars`, GitHub variables, a Docker build argument, or source control. See [Secrets Manager secret creation and updates](https://docs.aws.amazon.com/secretsmanager/latest/userguide/create_secret.html).

```json
{
  "SUPABASE_URL": "https://your-project.supabase.co",
  "SUPABASE_ANON_KEY": "your-public-anon-or-publishable-key",
  "SUPABASE_SERVICE_ROLE_KEY": "server-only-service-role-key",
  "SUPABASE_DB_URL": "postgresql://...transaction-pooler...?sslmode=require",
  "QDRANT_API_KEY": "private-qdrant-key",
  "GEMINI_API_KEY": "private-gemini-key",
  "GROQ_API_KEY": "private-groq-key",
  "GROQ_API_KEYS": "",
  "XAI_API_KEY": "",
  "BYOK_ENCRYPTION_KEY": "base64url-encoded-32-byte-key",
  "PROMO_HMAC_PEPPER": "long-random-secret",
  "OWNER_BOOTSTRAP_USER_ID": ""
}
```

Use the real Supabase transaction-pooler URI with TLS. For `llm_provider = "xai"`, supply `XAI_API_KEY` and change `llm_model`; for Groq, `GROQ_API_KEY` is required. Optional extra Groq credentials can be supplied as comma-separated or newline-separated values in the string field `GROQ_API_KEYS`; the application advances to another Groq credential only after a 401 authentication failure. It never rotates credentials on a 429, shared cooldown, or provider outage, and must not be used to bypass provider limits. The XAI field can remain empty when Groq is selected. The JSON fields must exist even if an unused provider field is an empty string. Generate BYOK/HMAC secrets with a trusted password manager or secrets tool; never reuse them in another environment. The Redis URL is injected from the private TLS ElastiCache endpoint by the task definition.

If you need the admin portal, create/sign up the owner account first, copy its Supabase Auth UUID into `OWNER_BOOTSTRAP_USER_ID`, update the secret, and redeploy the API and worker. Don't use test/demo credentials for the public owner account.

## 5. Build and start the containers

1. Run the GitHub Actions workflow **Build and deploy MindMesh to AWS ECS** manually with `deploy` unchecked. It builds and pushes the web, API, and worker images to ECR; ECR scans images on push. The website Dockerfile refuses builds without cloud mode, HTTPS URLs, a public Supabase key, and real privacy contact details.
2. Confirm the JSON Secrets Manager value is complete and migrations/provider connectivity are ready.
3. Set `deploy_services = true` in `infra/aws/terraform.tfvars`, then create and review another plan before applying:

   ```powershell
   Set-Location infra/aws
   terraform plan -out services.tfplan
   terraform show services.tfplan
   terraform apply services.tfplan
   terraform output
   Set-Location ../..
   ```

   This starts one web task, one API task, and one worker task. API/web scale on CPU; worker count is an operator setting until queue-depth autoscaling is implemented.
4. Verify Route 53 resolves both names and ACM status is `Issued`. Wait for ECS services to report steady state and ALB targets healthy.
5. For each subsequent GitHub Actions release, check `deploy` to force ECS to pull the new `prod` image tags. The workflow also pushes the immutable commit SHA tags for traceability.

If you set `alert_email` in `infra/aws/terraform.tfvars`, open **Amazon SNS → Topics → mindmesh-production-alerts → Subscriptions** and confirm the AWS email subscription. Without a confirmed subscription, alarms exist but will not notify that inbox.

In the AWS console, the first rollout should appear under **Elastic Container Service → Clusters → mindmesh-production → Services**. Wait for the API, web, and worker services to report steady state. Then open **EC2 → Load Balancers → mindmesh-production-public → Target groups** and confirm the API and web targets are healthy. In **EC2 → Load Balancers → Listeners**, verify HTTPS 443 forwards by host and HTTP 80 redirects to HTTPS. ECS Fargate services with `awsvpc` networking use IP target groups behind an Application Load Balancer; see [ECS service load balancing](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/service-load-balancing.html).

## 6. Launch checks and rollback

Before deploying the Groq usage dashboard, apply `backend/migrations/202610140003_llm_usage_analytics.sql` to the configured Supabase/Postgres database. Configure `GROQ_API_KEY` and, if needed, newline-separated `GROQ_API_KEYS` as backend Secrets Manager values. Terraform examples select `openai/gpt-oss-20b`; check the live Groq project limits and configure the shared Redis safety budgets before increasing service counts. See [Groq production rollout](groq-production.md) for the full verification and rollback checklist.

Before sharing the site, test signup/login/OAuth/password reset, auth redirects, source reads/writes, YouTube and Instagram jobs, uploads, AI chat, job retries, account isolation, admin authorization, consent/privacy flows, contact form, and 404 behavior on the actual HTTPS host. Check CloudWatch logs/alarms, Redis/database connectivity, Qdrant, provider quotas, and worker completion. Run the read-only k6 load scenario only against isolated staging; it does not load-test ingestion or paid AI calls.

Use **CloudWatch → Log groups → `/ecs/mindmesh-production/`** to inspect API, web, and worker logs; use **CloudWatch → Alarms** for configured AWS alarms. For WAF, open **WAF & Shield → Web ACLs → mindmesh-production-web-acl** and review sampled requests and blocked/rate-limited traffic. Do not expose task IPs directly: tasks run in private subnets and the public entry point is the ALB. See [ECS outbound networking](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/networking-outbound.html).

No production or staging AWS resources have been created from this workspace. The load test has not been run. Keep the old task-definition/image version available for rollback; for an incident, redeploy the previous image SHA and inspect ECS/ALB/CloudWatch before routing traffic back.

## Important application limitations to account for

- Core sources, notes, conversations, and graph state still use the legacy `mm_state` JSON document. Normalized-table indexes are not active for those reads/writes yet. A new cloud launch can use that path, but large-tenant performance must be load-tested before assuming it will scale.
- The worker service polls Postgres and handles one job at a time per ECS worker task. Increase worker replicas only after checking DB pool budget, CPU/memory, provider quotas, and job claim behavior.
- The public privacy notice and FAQ remain drafts. Do not publish until the legal identity, contact, actual providers/data practices, and policies are confirmed.
- Payments are deliberately disabled in the AWS task configuration. Do not advertise paid plans until provider credentials, webhook URLs/signatures, and end-to-end billing have been set up and verified.
