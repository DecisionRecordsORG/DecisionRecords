# Changelog

All notable changes to Decision Records will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Relationship packs for non-technical teams: People & Policy, Finance & Procurement and Product & Customer, with new relationship classes (exception to, sets precedent for, funds, approves, constrains, responds to, takes priority over). They are offered in organization settings and stay off until an administrator selects them
- Helper text under the Title, Context, Decision and Consequences fields of both decision forms
- The app has a complete icon set: `favicon.ico`, an SVG icon, an Apple touch icon, 192 and 512 pixel icons and a web manifest. It had only an SVG icon, which is hard to see on dark browser tabs
- Messages from the website contact form, the "Get in touch" dialog and the in-app feedback dialog are stored before the notification email is sent, so a message is no longer lost when email is not set up or the send fails. No IP address or user agent is stored
- `/api/contact`, `/api/sponsorship` and `/api/feedback` accept an optional `team_focus` ("What does your team make decisions about?", up to 200 characters) and an optional `team_size` code, store them with the message and include the team focus in the contact and "Get in touch" notification emails
- Super admins have an Inquiries page listing stored messages newest first, with filters by form and status, a detail view, mark as handled, and delete with confirmation. Messages that were never emailed are marked "Not emailed". The dashboard shows how many inquiries are not handled
- Team profile: the first-admin onboarding dialog asks two optional questions, "What does your team make decisions about?" and team size, and says why ("It helps us build for teams like yours"). They can be skipped, and tenant admins can answer or change them later under Organization Settings > Team profile
- Super admins see a tenant's team profile in the tenant details, and an Interest summary at the top of the Inquiries page: tenants and inquiries by team size, inquiries by form, and the distinct team focus answers as they were typed
- "Can't sign in? Get help" link for people who are stuck before they are signed in: on the Community landing page, on every step of the sign-in page (email, passkey, password, request access, request sent, recovery, resend verification), on the setup and recovery link page including its expired, used and invalid link messages, and as "Get help" on the domain approval page. It opens the public support page (`https://decisionrecords.org/support`) in a new tab, so a half-filled form is kept, and passes the topic and, when the page knows them, the email address and the organisation's email domain. Nothing else is passed
- The link is shown on the hosted service only. A self-hosted installation shows no link, so its users are not sent to the hosted service's support. The app uses a `support_url` from `/api/features` when one is reported (an http(s) address replaces the link target, any other value hides the link); the server does not report one yet
- The landing page says what went wrong when a verification link has expired or is not valid, or when a sign-in with Slack, Google or Microsoft did not complete. It was opened with `?error=...` and showed nothing
- Data retention runs by itself. Once a day the application anonymises accounts whose 7-day deletion grace period is over, erases soft-deleted decisions and tenants after 30 days, deletes login history after 90 days and stored contact messages after 24 months. No cron job, secret or other service is needed, and with several workers or containers only one of them does a day's run
- Limits on the automatic run: when more accounts (10), decisions (50) or tenants (1) are waiting than the limit, or the oldest waiting item is more than 7 days overdue, the run leaves that category alone, records how many are waiting and carries on with the rest. Super admins change the limits under Data retention
- Super admins have a Data retention page: whether the automatic run is on, what is waiting now with the list of what would be erased, a notice for each held back category with a "Run now" action that states the number of items, the limits, and the last runs with counts, errors and duration
- Every retention run and every erasure is recorded (kind, id, for a tenant its domain, and row counts; never names, email addresses or content) in the new `retention_runs` and `retention_erasures` tables
- `RETENTION_AUTO_RUN=false` and a super admin setting turn the automatic run off
- `GET /api/superadmin/retention`, `POST /api/superadmin/retention/run` and `GET`/`PUT /api/admin/settings/retention` for super admins

### Changed
- The in-app data processing page describes the messages people send us and the optional organisation details: what is stored, why, the legal basis, that they are deleted after 24 months or with the organisation, and that Decision Records is the Data Controller for them
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
- Startup migration `2.3.0` creates the `inquiries` table and adds four team profile columns to `tenants` (`team_focus`, `team_size`, `team_profile_answered_at`, `team_profile_answered_by_id`) on existing SQLite and PostgreSQL databases. It runs by itself when the new version starts; no manual step is needed
- `/api/contact`, `/api/sponsorship` and `/api/feedback` answer 200 with the usual thank-you message once the message is stored, also when email is not configured or the send fails. They used to answer 503 or 500 and drop the message. They still answer 503 or 500 when the message could be neither stored nor emailed
- Personal data export includes the messages a user sent through the contact, "Get in touch" and feedback forms while signed in. Deleting an account removes the name, email address and message from that person's stored inquiries
- The in-app feedback dialog and the footer contact dialog say above the send button that the message is stored so it can be answered, and the team profile questions in the onboarding dialog and in organization settings carry a "How we handle your data" link. Both point to the Data Processing Addendum page (`/dpa`)
- The in-app feedback entry is called "Help and feedback" and its dialog no longer says a support ticket is created. It says "Ask for help, report a problem or tell us what you think. We read every message and reply by email unless you ask us not to." The consent box reads "You may reply to me by email" and the button "Send message"
- Terms of Service, section 6: says that messages sent to us and the optional organisation details are used to reply and to understand which kinds of teams use Decision Records, and refers to the Data Processing Agreement (linked to `/dpa`) instead of a privacy policy page that does not exist
- The data processing page gives `contact@decisionrecords.org` as its contact address, like the other legal pages
- Inquiries older than 24 months are deleted by the daily retention run, and reported as `purged_inquiries` by `/api/admin/execute-gdpr-tasks`
- `POST /api/admin/execute-gdpr-tasks` is optional now that retention runs by itself. Its authentication and the counts under `results` are unchanged. It follows the same limits as the automatic run, so it can leave a category alone, and its response adds `run_id`, `status`, `held_back` and `errors`. A JSON body `{"categories": [...]}` limits it to chosen categories
- Erasing an expired tenant now also erases its members' accounts (with their passkeys, consents, notification settings and sign-in history), its decisions with history, comments and links, its infrastructure entries, audit log, role and access requests, sign-in, SSO and email configuration, Slack and Teams connections and AI keys. The domain approval is kept without the requester's name and email, and messages its members sent lose their personal fields. Before, only memberships, settings and spaces were removed. A member who also belongs to another tenant is kept
- A soft-deleted tenant is erased only while its status is "deleted". One whose status was changed by hand is listed for review and left alone
- Anonymising an account also clears the decision owner fields that named the person, deletes their notification settings, setup links, pending email verifications and access requests, removes their Slack and Teams links, revokes their AI keys and removes the IP address from their consent records
- Soft-deleted decisions of a soft-deleted tenant are erased with the tenant, not one by one
- Startup migration `2.4.0` creates the `retention_runs` and `retention_erasures` tables on existing SQLite and PostgreSQL databases. It runs by itself when the new version starts
- Upgrading an installation where the cron job was never set up: the first automatic run deletes old login history and old stored messages and holds back overdue accounts, decisions and tenants until a super admin has looked at them. See "Data retention" in `docs/self-hosting.md`. Erasure cannot be undone, so take a database backup first

### Fixed
- On PostgreSQL the scheduled GDPR task failed with a foreign key error as soon as an expired tenant had a decision in a space, an audit log entry or a role request, or an expired decision had a relationship to another decision. The request answered 500 and everything after the failing step (tenants, login history) was skipped on every run. Each category now runs on its own and each account, decision and tenant in its own transaction, so one failure is rolled back, recorded and does not stop the rest
- Due dates are compared in UTC whatever time zone the PostgreSQL session uses. Before, on a server not set to UTC, every deadline was shifted by the session's offset, so data could be erased hours early. On such a server retention now also waits the size of the offset plus one hour past each due date, because dates written there are stored shifted
- Restoring a soft-deleted tenant (`POST /api/tenants/<domain>/restore`) always answered 500, because it tried to write an audit log entry without a user. It now restores the tenant and its decisions
- An account whose anonymised flag was empty (rows older than the column) was never picked up for anonymisation
- The cron secret is compared in constant time
- The user limit is now enforced when an account is created by Slack, Google, Microsoft or Teams sign-in, by a tenant's own SSO provider, by the Teams tab sign-in and by an emailed sign-up link. A full tenant refuses the new account with the "User limit reached" error; existing members can still sign in and the first account of a new organization is never refused
- The sign-in page and the access request list show what the user limit is when it stops an account from being added
- The email telling someone they were made a decision owner was never sent, because it failed while building the message
- Loading relationship settings no longer fails for a tenant whose custom relationship class uses the same key as a built-in class added later; the tenant's own class is used
- Community Edition could not initialise its database on a PostgreSQL server without TLS, which is the setup shown in the self-hosting guide: the start-up connection check forced `sslmode=require` whatever `DATABASE_URL` said, and `/health` stayed unhealthy. The check now uses the same connection settings as the rest of the application, so `sslmode` in `DATABASE_URL` decides
- A rate-limited request was answered with 500 "An internal server error occurred" instead of 429, and a request with the wrong HTTP method with 500 instead of 405. HTTP errors now keep their status. API paths answer `{ "error": ... }`, and a 429 says "Too many requests. Please wait a minute and try again." with a `Retry-After` header, which is what the sign-in pages and the contact and feedback forms now show
- `/api/sponsorship` answered 500 when an optional field was sent as JSON `null`, and `/api/feedback` answered 500 for `null` fields and for a body that was not JSON. All three form endpoints now treat missing, `null` and wrong-typed optional fields as not given and answer 400 for an invalid body
- End-to-end tests: the sign-in helpers typed into the server-rendered form before the app was running, lost the text when it started, and timed out on a disabled button. They now fill the form until the app has taken the values
- The first-admin onboarding dialog no longer opens on top of another dialog, such as a decision someone has started writing, and no longer takes the keyboard focus from it. It waits until that dialog is closed. Its buttons stay in view on short windows
- Signing in through an organisation's own single sign-on provider answered 500 "Authentication failed" on every installation that serves the built frontend, after the account had been created or found. The redirect after sign-in named a page that exists only without a frontend build. The person is now signed in and sent to their organisation. The super admin sign-in form had the same fault
- When an organisation is at its user limit, its own single sign-on provider now sends a newcomer to the sign-in page with the user limit message, like the other sign-in methods, instead of a bare error page
- Tests no longer depend on whether a frontend build exists in the checkout, and one group of tests runs the app with a built frontend, as production does. A test fails when a redirect names a page that exists in only one of the two configurations
- After recovering an account with a new password, the person was treated as still setting up their account for up to 30 minutes: signing in led to the profile page in setup mode instead of the organisation's decisions. Setting a password from a recovery link now ends the setup session, as setting up a passkey already did
- The answer to a validated recovery link named a page, `/<domain>/recover`, that the app does not have. Recovery and first-time setup share the setup page, and the server now names that page for both. The emailed recovery link already pointed there
- End-to-end tests: the helper that creates an account without credentials returned a setup token that was never stored, so the setup page could only be tested in its error state. It returns a working token, and a second test-only helper creates a setup or recovery link for an existing account

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
