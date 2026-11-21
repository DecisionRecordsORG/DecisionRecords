# Changelog

All notable changes to Decision Records will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Relationship packs for non-technical teams: People & Policy, Finance & Procurement and Product & Customer, with new relationship classes (exception to, sets precedent for, funds, approves, constrains, responds to, takes priority over). They are offered in organization settings and stay off until an administrator selects them
- Helper text under the Title, Context, Decision and Consequences fields of both decision forms
- The app has a complete icon set: `favicon.ico`, an SVG icon, an Apple touch icon, 192 and 512 pixel icons and a web manifest. It had only an SVG icon, which is hard to see on dark browser tabs

### Changed
- The default user limit per tenant is 25 instead of 5. Installations that never saved a limit follow the new default; a saved limit, including a saved 5, is kept. Super admins can still change it (0 = unlimited)
- The user limit counts every account that belongs to a tenant. Accounts admitted through access requests were not counted before, so a tenant could grow past its limit
- Notification emails say "decision" and "decision record" and drop the "[ADR]" subject prefix: "New decision: <title>", "Decision updated: <title>", "Decision status changed: <title> is now <status>". They refer to a decision by the ID shown in the app
- New email configurations and passkey settings use "Decision Records" as the default display name. On startup, a stored email from-name, passkey display name or default space description that still equals the old default is updated; names an administrator chose are kept
- Decision form placeholders, the app title and description, the landing page, the README and settings copy describe decision records for any team instead of architecture decisions. The README keeps a section on the ADR format and arc42 for software teams
- The login screen and the empty decision list use a neutral document icon
- The Core relationship pack is described as fitting any kind of decision, and the settings tab calls the packs "Relationship Packs"
- Terms of Service and Service Level Agreement pages describe a free plan for teams of up to 25 users in place of the limited preview
- `requirements.txt` pins every installed package to an exact version, including packages that are only installed as dependencies and the `gunicorn` server; the Community image no longer installs anything outside that file
- CI and the release workflow now also start the built Community image against a PostgreSQL container with a `postgresql://` `DATABASE_URL`, and require `/health` to report a connected database, before the release workflow publishes anything
- CI runs the fixture-based backend tests against PostgreSQL as well as SQLite (`TEST_DATABASE_URL`)
- The Enterprise deploy workflow starts the new image against PostgreSQL before it publishes or deploys anything, verifies the database health route after the restart, and restores the previous image automatically when the new one is not healthy

### Fixed
- The user limit is now enforced when an account is created by Slack, Google, Microsoft or Teams sign-in, by a tenant's own SSO provider, by the Teams tab sign-in and by an emailed sign-up link. A full tenant refuses the new account with the "User limit reached" error; existing members can still sign in and the first account of a new organization is never refused
- The sign-in page and the access request list show what the user limit is when it stops an account from being added
- The email telling someone they were made a decision owner was never sent, because it failed while building the message
- Loading relationship settings no longer fails for a tenant whose custom relationship class uses the same key as a built-in class added later; the tenant's own class is used
- Community Edition could not initialise its database on a PostgreSQL server without TLS, which is the setup shown in the self-hosting guide: the start-up connection check forced `sslmode=require` whatever `DATABASE_URL` said, and `/health` stayed unhealthy. The check now uses the same connection settings as the rest of the application, so `sslmode` in `DATABASE_URL` decides
- A rate-limited request was answered with 500 "An internal server error occurred" instead of 429, and a request with the wrong HTTP method with 500 instead of 405. HTTP errors now keep their status. API paths answer `{ "error": ... }`, and a 429 says "Too many requests. Please wait a minute and try again." with a `Retry-After` header, which is what the sign-in pages and the contact and feedback forms now show

## [2.1.1] - 2026-11-21

### Security
- Passkey registration now requires proof of account control: a signed-in session for the same account, or a valid setup or recovery link. Anonymous registration can only create the first account of a new organisation
- Account setup links for access requests are delivered only by email to the requester or shown to the administrator who approves the request; they are never returned in the response to the request
- Sign-in with Slack, Google, Microsoft and Teams only redirects to same-site paths afterwards

### Fixed
- Community Docker image failed at startup with `ModuleNotFoundError: No module named 'decision_relationships'` because the module was not copied into the image. `Dockerfile.community` now ships every root Python module
- Saving SMTP settings in Community Edition returned a 500 error because the encryption key lookup required a private Enterprise module. The key is now read from `SMTP_ENCRYPTION_KEY`
- `python run_local.py` crashed in a checkout without the private `ee/` modules. It now runs Community Edition when they are absent
- Release notes, README and CONTRIBUTING documented build and run commands that only worked with the private `ee/` modules or a full source checkout
- A freshly built image could not connect to PostgreSQL (`ImportError: no pq wrapper available`): unpinned SQLAlchemy resolved to 2.1, which selects the psycopg 3 driver for `postgresql://` URLs. SQLAlchemy and the PostgreSQL drivers are now pinned
- Sessions created by Teams sign-in, by setting a password from a setup link and by registering a first passkey from a setup link were cleared on the next request
- Signing in once with Slack, Google or Microsoft no longer disables passkey sign-in for an account that has a password or passkey
- First-time Teams sign-in for a new account returned a 500 error
- Decision forms no longer lose unsaved input: Esc, a backdrop click, the X and Cancel buttons all ask before discarding changes (including owner, spaces and relationships), and the full-page form asks before navigating away or unloading the page
- Any tenant member can now pick a Decision Owner; the picker uses a new tenant-scoped `GET /api/tenant/members` endpoint that returns only member ids and display names
- The delete confirmation now describes what actually happens: the decision is hidden immediately and permanently erased after 30 days, with no restore option in the app
- The contact form now sends its message: `POST /api/contact` emails the configured Contact Form Email address, and the footer shows an error and keeps the text when sending fails

### Changed
- CI and the release workflow now start the built Community image and require it to answer `/api/health` before the release workflow publishes anything
- New `scripts/check_ce_image_modules.py` check fails when a module imported by `app.py` is not shipped by `Dockerfile.community`
- In organisations that enforce single sign-on, passkey sign-in is refused for every account
- Without system email configured, an access request always waits for an administrator, who is shown the setup link to pass on

## [2.1.0] - 2026-08-09

### Added
- Configurable decision relationship packs in Community Edition, including default relationship classes for engineering, product, operations, security, and governance workflows
- ADR supersede flows that let authors mark an existing decision as overridden directly from the create and edit UI
- Relationship-aware decision detail and list views so linked, superseded, and superseding ADRs are visible without leaving the record
- MCP decision relationship tools for listing, linking, and superseding decisions programmatically

### Changed
- Shared-core decision APIs now persist relationship metadata and update decision status consistently when a supersede link is created
- Tenant settings can now store relationship pack selection and custom relationship classes for organization-specific workflows

## [2.0.28] - 2026-03-03

### Added
- GDPR Art. 17: Account deletion with 7-day grace period and anonymisation
- GDPR Art. 20: One-click personal data export (JSON)
- GDPR Art. 7: Consent management (analytics, AI processing, email notifications)
- Cookie consent banner with PostHog conditional loading
- Automated GDPR task execution endpoint (scheduled anonymisation, history cleanup, expired record purge)
- UserConsent model and automatic Community Edition database migration for consent tables
- Breach notification procedure documentation
- Data Protection Impact Assessments (AI/LLM, Analytics, Integrations)
- Sub-processor list documentation
- GDPR backend test suite (67 tests)
- GDPR E2E test suite (11 tests)

## [2.0.27]

### Added
- Open source release under BSL 1.1 license
- Community Edition with core ADR functionality
- Docker support for self-hosting
- Self-hosting documentation

### Changed
- Restructured codebase for open core model
- Enterprise features moved to separate private repository

## [1.15.0] - 2026-01-09

### Added
- Initial open source release
- Architecture Decision Records (ADR) management
- Multi-tenant support
- WebAuthn/Passkey authentication
- Generic OIDC SSO integration
- Role-based access control (Governance model)
- Spaces for organizing decisions
- Audit logging
- Email notifications
- IT Infrastructure mapping
- Docker Compose for easy self-hosting
- SQLite support for simple deployments
- PostgreSQL support for production deployments

### Security
- CSRF protection
- Input sanitization
- Rate limiting ready

---

## Version History Format

Each release includes:

### Added
New features and capabilities

### Changed
Changes to existing functionality

### Deprecated
Features that will be removed in future versions

### Removed
Features that have been removed

### Fixed
Bug fixes

### Security
Security-related changes and fixes

---

[Unreleased]: https://github.com/DecisionRecordsORG/DecisionRecords/compare/v2.1.1...HEAD
[2.1.1]: https://github.com/DecisionRecordsORG/DecisionRecords/compare/v2.1.0...v2.1.1
[2.1.0]: https://github.com/DecisionRecordsORG/DecisionRecords/compare/v2.0.28...v2.1.0
[2.0.28]: https://github.com/DecisionRecordsORG/DecisionRecords/compare/v2.0.27...v2.0.28
[2.0.27]: https://github.com/DecisionRecordsORG/DecisionRecords/compare/v1.15.0...v2.0.27
[1.15.0]: https://github.com/DecisionRecordsORG/DecisionRecords/releases/tag/v1.15.0
