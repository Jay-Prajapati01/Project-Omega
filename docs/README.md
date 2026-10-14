# Documentation index

- [Architecture and setup](architecture-and-setup.md) — app structure, tenant model, roles, and service configuration.
- [YouTube](features/youtube.md) — extraction, transcript fallback, and storage flow.
- [Instagram](features/instagram.md) — public post extraction, OCR/speech, and storage flow.
- [Ask AI](features/ask-ai.md) — retrieval augmented answer generation.
- [Stored](features/stored.md) — saved source and note views, search, and tenant ownership.
- [Knowledge Graph](features/knowledge-graph.md) — source-correct YouTube/Instagram clusters, thumbnails, and rebuilding older graph relationships.
- [Admin and multi-tenancy](admin-and-multi-tenancy.md) — identity, scope propagation, admin controls, and current portal surface.
- [Admin analytics setup](admin-analytics-launch.md) — consent-based metrics, local/cloud storage, and launch setup.
- [Android companion](companion.md) — app behavior and YouTube/Instagram-only link handling.
- [Manual setup checklist](manual-setup.md) — Supabase/Google sign-in, local services, and USB phone testing.
- [Production security](production-security.md) — rate limits, quotas, provider protections, AWS WAF, Cloud Armor, and monitoring.
- [Groq production rollout](groq-production.md) — GPT-OSS 20B configuration, shared Redis budgets, API Key Analytics, migration, verification, and rollback.
- [Scaling readiness](scaling-readiness.md) — database/index status, safe caching, load-test sequence, and host capacity checks.
- [AWS deployment](aws-deployment.md) — ECS/Fargate, ALB/WAF, Redis, secrets, GitHub OIDC, and launch prerequisites.
- [Google Cloud deployment](gcp-deployment.md) — Cloud Run, Cloud Tasks, Cloud Run Jobs, Memorystore, Cloud Armor, GitHub WIF, and launch prerequisites.
- [Website launch checklist](website-launch-checklist.md) — SEO, consent-gated analytics, privacy, and launch verification.
- [Pipelines and tools](pipelines-and-tools.md) — shared processing stages, dependencies, and runtime boundaries.
- [Known issues and fixes](known-issues-and-fixes.md) — observed UI, retrieval, graph, and companion problems and their current resolutions.
