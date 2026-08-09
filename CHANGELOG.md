# Changelog

All notable changes to Decision Records will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/DecisionRecordsORG/DecisionRecords/compare/v2.1.0...HEAD
[2.1.0]: https://github.com/DecisionRecordsORG/DecisionRecords/compare/v2.0.28...v2.1.0
[2.0.28]: https://github.com/DecisionRecordsORG/DecisionRecords/compare/v2.0.27...v2.0.28
[2.0.27]: https://github.com/DecisionRecordsORG/DecisionRecords/compare/v1.15.0...v2.0.27
[1.15.0]: https://github.com/DecisionRecordsORG/DecisionRecords/releases/tag/v1.15.0
