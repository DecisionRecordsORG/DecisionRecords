# Security Policy

## Supported Versions

We release patches for security vulnerabilities in the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 1.x.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

We take the security of Decision Records seriously. If you believe you have found a security vulnerability, please report it to us responsibly.

### How to Report

**Please DO NOT report security vulnerabilities through public GitHub issues.**

Instead, please report them via email to: **security@decisionrecords.org**

Include the following information in your report:

1. **Type of vulnerability** (e.g., SQL injection, XSS, authentication bypass)
2. **Location** of the affected source code (file path, line numbers if known)
3. **Step-by-step instructions** to reproduce the issue
4. **Proof-of-concept** or exploit code (if possible)
5. **Impact** of the vulnerability (what could an attacker achieve?)
6. **Your recommended fix** (if you have one)

### What to Expect

- **Acknowledgment**: We will acknowledge receipt of your report within 48 hours
- **Initial Assessment**: We will provide an initial assessment within 7 days
- **Regular Updates**: We will keep you informed of our progress
- **Resolution**: We aim to resolve critical vulnerabilities within 30 days
- **Credit**: We will credit you in our security advisory (unless you prefer to remain anonymous)

### Safe Harbor

We consider security research conducted in accordance with this policy to be:

- Authorized concerning any applicable anti-hacking laws
- Authorized concerning any relevant anti-circumvention laws
- Exempt from restrictions in our Terms of Service that would interfere with conducting security research

We will not pursue legal action against researchers who:

- Make a good faith effort to avoid privacy violations and disruptions to others
- Only interact with accounts they own or have explicit permission to access
- Do not exploit a vulnerability beyond what is necessary to demonstrate it
- Report vulnerabilities promptly and do not disclose them publicly before we've had a chance to fix them

## Security Best Practices for Self-Hosting

If you're self-hosting Decision Records, follow these security guidelines:

### Environment Configuration

```bash
# Always use strong, unique secrets
SECRET_KEY="<generate-a-32+-character-random-string>"

# Use HTTPS in production
# Configure your reverse proxy (nginx, Caddy, etc.) with SSL/TLS

# Set secure cookie settings (automatic when not in development mode)
ENVIRONMENT="production"
```

### Database Security

- Use a dedicated database user with minimal required permissions
- Enable SSL/TLS for database connections
- Regular backups with encryption at rest
- Keep PostgreSQL updated

### Network Security

- Run behind a reverse proxy (nginx, Caddy, Traefik)
- Use a Web Application Firewall (WAF) if possible
- Restrict database access to application servers only
- Use private networks for internal communication

### Authentication

- Enable WebAuthn/Passkeys for passwordless authentication
- Configure SSO/OIDC with your identity provider
- Enforce strong password policies if using local auth
- Enable audit logging to track access

### Updates

- Subscribe to our security advisories
- Keep the application updated to the latest version
- Monitor dependencies for known vulnerabilities

## Security Features

Decision Records includes several built-in security features:

### Authentication & Authorization
- WebAuthn/Passkey support for phishing-resistant authentication
- OIDC/SSO integration for enterprise identity providers
- Role-based access control (RBAC) with granular permissions
- Session management with secure cookies

### Data Protection
- Input sanitization to prevent XSS attacks
- Parameterized queries to prevent SQL injection
- CSRF protection on all state-changing operations
- Content Security Policy (CSP) headers

### Audit & Compliance
- Comprehensive audit logging
- Login history tracking
- Admin action logging

### Infrastructure (Enterprise Edition)
- Azure Key Vault integration for secrets management
- Cloudflare integration for DDoS protection and WAF

## Vulnerability Disclosure Timeline

1. **Day 0**: Vulnerability reported
2. **Day 1-2**: Acknowledgment sent
3. **Day 3-7**: Initial assessment and severity classification
4. **Day 7-30**: Fix development and testing
5. **Day 30+**: Coordinated disclosure (after fix is released)

For critical vulnerabilities (CVSS 9.0+), we aim to release a patch within 7 days.

## Contact

- Security issues: security@decisionrecords.org
- General questions: support@decisionrecords.org
- PGP Key: Available upon request

Thank you for helping keep Decision Records and our users safe!
