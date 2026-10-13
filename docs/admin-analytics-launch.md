# Admin analytics launch setup

## What the dashboard measures

The owner/admin portal at `/admin` shows consented, anonymous usage totals. It refreshes every five seconds while the tab is visible. “Online” means a browser interacted with the site and sent an activity heartbeat in the previous five minutes; it is an estimate, not a live connection count. The daily chart uses UTC days. Page and feature tables use a rolling 30-day window; total visitors are unique random browser IDs seen since analytics began.

The browser sends only a random UUID, an allowlisted page path, and (for feature events) one of `youtube`, `instagram`, `ask_ai`, or `stored`. Query strings and source IDs are discarded. Names, email addresses, chat text, saved URLs, IP addresses, and account IDs are not included in analytics records. Collection starts only after the visitor accepts the analytics prompt; declining leaves analytics off. Visitors can revisit Cookie settings in the landing-page footer.

## Storage setup

In local execution mode, the backend automatically creates `backend/data/analytics.sqlite3`; no database migration is needed to use the local analytics page. Back up or delete that file according to your local data needs.

When deploying in cloud execution mode, apply the migration once to the Supabase/Postgres database connected to the backend. You can paste the contents of `backend/migrations/202610140001_analytics.sql` into Supabase Dashboard → SQL Editor → New query, then run it; or use the command below from PowerShell:

```powershell
psql "$env:SUPABASE_DB_URL" -v ON_ERROR_STOP=1 -f "backend/migrations/202610140001_analytics.sql"
```

Use the database connection string from the backend's secret environment; do not paste it into source control or the frontend environment. The migration creates a table with RLS enabled and grants direct table access only to `service_role`. FastAPI writes events and only returns aggregate results after checking the signed-in account's owner/admin role. The browser never receives database credentials or raw event rows.

If the backend's configured database connection is rejected during deployment, correct the backend's private `SUPABASE_DB_URL` secret in deployment settings, restart the backend, and run the migration in the Supabase SQL Editor while signed in as a database owner. Do not put a database password in a `NEXT_PUBLIC_*` variable.

After deploying and applying the migration, sign in as an owner/admin, accept analytics in the consent prompt, visit several pages/features, and open `/admin`. The dashboard should update without a manual refresh. In cloud mode, a 503 message means the migration or backend database connection is not ready.

## Data retention and later GA4 setup

The current table does not automatically delete old records. Before public launch, choose a retention period and schedule a database cleanup, for example:

```sql
delete from public.mm_analytics_events
where occurred_at < now() - interval '13 months';
```

This retains aggregate history only for that period. Review the privacy notice and legal requirements for the markets you serve. When a production domain is available, GA4 can be configured separately using `NEXT_PUBLIC_GA_MEASUREMENT_ID`; the existing consent gate loads it only after acceptance. Never put a GA admin/service credential in the frontend.

## Pricing visibility

Public pricing has been removed from the landing page, navigation, sitemap, and FAQ. A direct visit to `/pricing` returns to the landing page. Existing in-account usage and billing/settings areas remain available for current plan limits; payment checkout remains disabled until it is deliberately configured.
