# Website launch checklist

This checklist tracks the website items from the launch review. Source-code work is prepared; items that require your real domain, accounts, or business details remain marked as launch tasks.

## Implemented in the app

- Custom Next.js not-found page (verify it returns HTTP 404 on the deployed host).
- Titles and descriptions for public pages: home, contact, FAQ, and privacy. Public pricing is intentionally deferred; `/pricing` redirects to the landing page.
- Open Graph and X/Twitter share metadata with a 1200 × 630 branded preview at `/share-card.png`.
- `sitemap.xml` and `robots.txt`; sitemap and sitemap reference are emitted only after setting a valid HTTPS `NEXT_PUBLIC_SITE_URL`. No site-wide `Disallow: /` rule is present. Private app paths and `/thank-you` are excluded from crawling.
- Contact form client/server validation, per-IP rate limit already present in the backend, honeypot, and thank-you route.
- Consent-gated first-party analytics and optional GA4 loader: neither collects browser events before acceptance; contact conversion is emitted only after consent and on the contact thank-you route. GA4 remains disabled if no measurement ID is configured.
- Draft FAQ and privacy notice; FAQ markup uses ordinary disclosure elements and does not add FAQ structured data.
- Customer-stories placeholder explicitly says no reviews are published; no endorsements have been invented.
- Meaningful descriptions on content thumbnails. Brand marks next to visible MindMesh text remain decorative.

## Required before a real launch

1. Deploy the frontend and backend, connect a real domain, configure DNS and TLS, and set `NEXT_PUBLIC_SITE_URL` to the canonical HTTPS origin. Configure the hosting/CDN to redirect HTTP to HTTPS and verify there is no mixed content.
2. Set `NEXT_PUBLIC_PRIVACY_BUSINESS_NAME` and `NEXT_PUBLIC_PRIVACY_CONTACT_EMAIL`. Replace the draft privacy text with the actual data inventory, retention/deletion policy, active providers and regions, legal basis, and applicable rights. Obtain appropriate legal review.
3. Create a GA4 property if desired, set `NEXT_PUBLIC_GA_MEASUREMENT_ID` to its real `G-…` ID, and verify consent behavior and the `generate_lead` conversion in GA4 DebugView. First-party anonymous admin metrics work independently; GA4 remains disabled when no measurement ID is set.
4. Add the production domain as a property in Google Search Console, verify domain ownership using DNS, submit `https://YOUR_DOMAIN/sitemap.xml`, and inspect important public URLs after deployment.
5. Review the FAQ answers against the live product, policies, and limitations. The current questions are drafts based on visible app behavior, not customer research. Add public pricing only after choosing plans and limits from launch evidence.
6. Keep the customer stories placeholder until real customers provide genuine feedback and explicit permission for the exact quote and attribution.
7. Verify `/does-not-exist` returns 404, public page metadata and share previews resolve on the live domain, contact validation/rate-limit/honeypot behavior works, GA is blocked before consent, and accepted/rejected preferences persist.
8. Check all production flows on desktop and mobile, inspect browser console/network errors, confirm backend Redis/shared rate limiting and quotas are configured, and ensure secrets exist only in server-side environment variables.

## Environment values

Configure these in the frontend deployment environment (not in a committed secrets file):

```dotenv
NEXT_PUBLIC_SITE_URL=https://your-real-domain.example
NEXT_PUBLIC_GA_MEASUREMENT_ID=
NEXT_PUBLIC_PRIVACY_BUSINESS_NAME=
NEXT_PUBLIC_PRIVACY_CONTACT_EMAIL=
```

The domain shown above is an example only. Do not ship the example host or blank privacy identity fields. Submit the sitemap only after the real site is live and Search Console ownership is verified.
