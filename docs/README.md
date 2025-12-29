# Architecture Decisions Application - Documentation

Welcome to the comprehensive documentation for the Architecture Decisions multi-tenant application. This documentation covers all features, deployment procedures, and administrative functions.

## 📚 Documentation Index

### Core Features
- [**Authentication & SSO**](./authentication.md) - WebAuthn/Passkeys, Local auth, and SSO integration
- [**Multi-Tenant Architecture**](./multi-tenant.md) - Domain-based tenant isolation and management
- [**Email Configuration**](./email-configuration.md) - SMTP setup with Azure Key Vault integration
- [**Security Features**](./security.md) - Comprehensive security implementation
- [**Product Analytics**](./analytics.md) - PostHog integration with privacy-respecting tracking

### Deployment & Infrastructure
- [**Azure Deployment Guide**](./azure-deployment.md) - Complete Azure Container Instances deployment
- [**Azure Key Vault Integration**](./key-vault.md) - Secure credential management
- [**Infrastructure Overview**](./infrastructure.md) - Network, database, and container configuration

### Administration
- [**Super Admin Guide**](./super-admin.md) - Master account management and system configuration
- [**Tenant Admin Guide**](./tenant-admin.md) - Organization-level administration
- [**Domain Approval Workflow**](./domain-approval.md) - New organization onboarding

## 🚀 Quick Start

### Access URLs
- **Production**: https://decisionrecords.org
- **Super Admin**: https://decisionrecords.org/superadmin

### Key Features

#### 🔐 Authentication
- **Passwordless**: WebAuthn/Passkeys support
- **SSO Integration**: OIDC-compliant SSO
- **Multi-factor**: Built-in MFA with passkeys
- **Local Auth**: Traditional email/password option

#### 🏢 Multi-Tenancy
- **Domain Isolation**: Complete data separation by organization domain
- **Tenant Management**: Super admin oversight of all organizations
- **Custom Branding**: Per-tenant customization capabilities

#### 📧 Email System
- **Azure Key Vault**: Secure SMTP credential storage
- **Notification System**: Automated email notifications
- **Template Support**: HTML and plain text email templates
- **Test Functionality**: Built-in email testing

#### 🛡️ Security
- **CSRF Protection**: Automatic token management
- **Input Sanitization**: Comprehensive XSS prevention
- **Rate Limiting**: API abuse prevention
- **Security Headers**: Enhanced HTTP security
- **Tenant Isolation**: Strict data access controls

## 📖 Architecture Overview

```
┌─────────────────────────────────────────────────┐
│              Application Gateway                 │
│                 (Azure WAF)                      │
└──────────────────┬──────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────┐
│          Container Instance (ACI)                │
│        ┌─────────────────────────┐              │
│        │   Flask Application     │              │
│        │   + Angular Frontend    │              │
│        └───────────┬─────────────┘              │
│                    │                             │
│        ┌───────────▼─────────────┐              │
│        │   Managed Identity      │              │
│        └───────────┬─────────────┘              │
└────────────────────┼────────────────────────────┘
                     │
        ┌────────────┼────────────┐
        │            │            │
┌───────▼────┐ ┌────▼─────┐ ┌───▼──────┐
│ PostgreSQL │ │ Key Vault│ │   Logs   │
│  Database  │ │  Secrets │ │ Analytics│
└────────────┘ └──────────┘ └──────────┘
```

## 🔧 Technology Stack

### Backend
- **Framework**: Flask 3.0.0
- **Database**: PostgreSQL with psycopg2
- **ORM**: SQLAlchemy
- **Security**: Flask-Limiter, Flask-Talisman, bleach
- **Authentication**: Authlib, WebAuthn
- **Cloud**: Azure SDK for Python

### Frontend
- **Framework**: Angular 18
- **UI Components**: Angular Material
- **Authentication**: WebAuthn API
- **HTTP**: Built-in interceptors for CSRF

### Infrastructure
- **Container**: Azure Container Instances
- **Gateway**: Azure Application Gateway with WAF
- **Database**: Azure Database for PostgreSQL
- **Secrets**: Azure Key Vault
- **Registry**: Azure Container Registry
- **Network**: Azure Virtual Network with NSG

## 📝 Version History

### Latest Release
- **Security Framework**: Complete security implementation
- **Super Admin Email**: Configurable notification email
- **CSRF Protection**: Automatic token management
- **Azure Key Vault**: SMTP credential security
- **Domain Approval**: Streamlined onboarding workflow

## 🤝 Contributing

For development setup and contribution guidelines, see the [Development Guide](./development.md).

## 📞 Support

For issues or questions:
- Create an issue in the repository
- Contact the super admin through the application
- Review troubleshooting guides in the documentation

---

*Last Updated: December 2024*
