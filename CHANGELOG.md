# Changelog

All notable changes to Decision Records will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2.28.0] - 2026-03-03

### Added
- GDPR Art. 17: Account deletion with 7-day grace period and anonymisation
- GDPR Art. 20: One-click personal data export (JSON)
- GDPR Art. 7: Consent management (analytics, AI processing, email notifications)
- Cookie consent banner with PostHog conditional loading
- Automated GDPR task execution endpoint (scheduled anonymisation, history cleanup, expired record purge)
- UserConsent model and database migration (`ee/scripts/migrate_to_v228.py`)
- Breach notification procedure documentation
- Data Protection Impact Assessments (AI/LLM, Analytics, Integrations)
- Sub-processor list documentation
- GDPR backend test suite (67 tests)
- GDPR E2E test suite (11 tests)

## [2.27.0]

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

[Unreleased]: https://github.com/DecisionRecordsORG/DecisionRecords/compare/v2.28.0...HEAD
[2.28.0]: https://github.com/DecisionRecordsORG/DecisionRecords/compare/v2.27.0...v2.28.0
[2.27.0]: https://github.com/DecisionRecordsORG/DecisionRecords/compare/v1.15.0...v2.27.0
[1.15.0]: https://github.com/DecisionRecordsORG/DecisionRecords/releases/tag/v1.15.0