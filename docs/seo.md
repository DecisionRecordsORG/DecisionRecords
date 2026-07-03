# Public Website SEO Plan

The public website should be indexable, fast to crawl, and clear about the open-source Community Edition.

## Indexable Pages

Include only public, durable pages in the sitemap:

- `/`
- `/security-features`
- `/security`
- `/terms`
- `/dpa`
- `/sla`

Do not index setup, admin, tenant, auth, or API routes.

## Technical SEO

- Every public route should set a route-specific title, description, canonical URL, Open Graph metadata, and Twitter card metadata.
- `robots.txt` should allow the public site and block setup/admin/API routes.
- `sitemap.xml` should list only indexable public routes.
- The Angular prerender route list should be explicit so app-only routes are not emitted as static marketing pages.
- Social preview images should point to real built assets. The default image is `/assets/og-image-default.png`.

## Content Direction

The homepage should make these points visible in the first viewport:

- Decision Records is open source.
- The Community Edition source is available on GitHub.
- The product helps teams preserve the reasoning behind architecture decisions.
- Commercial modules can exist without hiding or weakening the open-source core.

Future content pages worth adding:

- `/docs` for self-hosting and contribution guides.
- `/integrations` for a public overview of Slack, Teams, AI, and SSO modules without exposing proprietary implementation.
- `/faq` for licensing, Community Edition limits, and commercial module positioning.
- `/blog` only after there is an editorial workflow and a stable deployment path.

## Validation

Before deployment:

```bash
cd frontend
npm run build -- --configuration=community --progress=false
```

Then confirm that the build output contains:

- `dist/frontend/browser/index.html`
- `dist/frontend/browser/robots.txt`
- `dist/frontend/browser/sitemap.xml`
- `dist/frontend/browser/assets/og-image-default.png`
