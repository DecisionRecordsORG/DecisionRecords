# Email Configuration Guide

This guide covers the email system setup, configuration, and integration with Azure Key Vault for secure credential management.

## Table of Contents
- [Overview](#overview)
- [Azure Key Vault Integration](#azure-key-vault-integration)
- [SMTP Configuration](#smtp-configuration)
- [Email Templates](#email-templates)
- [Testing & Verification](#testing--verification)
- [Troubleshooting](#troubleshooting)

## Overview

The Architecture Decisions application uses a secure email system for:
- **User Notifications**: Welcome emails, password resets
- **Admin Alerts**: Domain approval requests, system notifications
- **System Health**: Test emails and monitoring alerts

### Key Features
- **Azure Key Vault Integration**: Secure SMTP credential storage
- **Managed Identity Access**: No hardcoded credentials
- **Template Support**: HTML and plain text email formats
- **Test Functionality**: Built-in email testing from admin panel
- **Error Handling**: Comprehensive logging and fallback mechanisms

## Azure Key Vault Integration

### Setup Process

#### 1. Create Azure Key Vault
```bash
# Create Key Vault
az keyvault create \
  --resource-group adr-resources-eu \
  --name adr-keyvault-eu \
  --location westeurope \
  --sku standard
```

#### 2. Store SMTP Credentials
```bash
# Store SMTP username
az keyvault secret set \
  --vault-name adr-keyvault-eu \
  --name "smtp-username" \
  --value "your-smtp-username"

# Store SMTP password
az keyvault secret set \
  --vault-name adr-keyvault-eu \
  --name "smtp-password" \
  --value "your-smtp-password"
```

#### 3. Configure Managed Identity Access
```bash
# Get container instance identity
IDENTITY_ID=$(az container show \
  --resource-group adr-resources-eu \
  --name adr-app-eu \
  --query identity.principalId -o tsv)

# Grant access to Key Vault
az keyvault set-policy \
  --name adr-keyvault-eu \
  --object-id $IDENTITY_ID \
  --secret-permissions get list
```

### Python Implementation

#### Key Vault Client
```python
# key_vault.py
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential

class KeyVaultClient:
    """Secure credential management with Azure Key Vault."""
    
    def __init__(self):
        self.vault_url = "https://adr-keyvault-eu.vault.azure.net/"
        self.credential = DefaultAzureCredential()
        self.client = SecretClient(
            vault_url=self.vault_url, 
            credential=self.credential
        )
    
    def get_smtp_credentials(self):
        """Retrieve SMTP credentials from Key Vault."""
        try:
            username = self.client.get_secret("smtp-username").value
            password = self.client.get_secret("smtp-password").value
            return username, password
        except Exception as e:
            logger.error(f"Failed to retrieve SMTP credentials: {e}")
            return None, None
```

#### Email Service Integration
```python
# app.py
def get_smtp_config():
    """Get SMTP configuration from Key Vault."""
    try:
        kv_client = KeyVaultClient()
        username, password = kv_client.get_smtp_credentials()
        
        if not username or not password:
            return None
            
        return {
            'SMTP_SERVER': 'smtp.gmail.com',
            'SMTP_PORT': 587,
            'SMTP_USERNAME': username,
            'SMTP_PASSWORD': password,
            'SMTP_USE_TLS': True
        }
    except Exception as e:
        logger.error(f"SMTP configuration failed: {e}")
        return None
```

## SMTP Configuration

### Supported SMTP Providers

#### Gmail
```python
SMTP_CONFIG = {
    'SMTP_SERVER': 'smtp.gmail.com',
    'SMTP_PORT': 587,
    'SMTP_USE_TLS': True
}
```

#### Outlook/Hotmail
```python
SMTP_CONFIG = {
    'SMTP_SERVER': 'smtp-mail.outlook.com',
    'SMTP_PORT': 587,
    'SMTP_USE_TLS': True
}
```

#### Custom SMTP Server
```python
SMTP_CONFIG = {
    'SMTP_SERVER': 'your.smtp.server.com',
    'SMTP_PORT': 587,  # or 465 for SSL
    'SMTP_USE_TLS': True,  # or SMTP_USE_SSL: True
}
```

### Configuration in Application

The SMTP settings are configured through the admin interface:

1. Navigate to Super Admin → Email Configuration
2. Enter SMTP server details
3. Test the configuration
4. Save settings

Settings are stored in the `SystemConfig` table:
```python
# Stored configuration keys
SMTP_SERVER = 'smtp_server'
SMTP_PORT = 'smtp_port'
SMTP_USE_TLS = 'smtp_use_tls'
SMTP_USERNAME = 'smtp_username'  # Reference to Key Vault
SMTP_PASSWORD = 'smtp_password'  # Reference to Key Vault
```

## Email Templates

### Template Structure
```
emails/
├── base.html           # Base template with styling
├── welcome.html        # User welcome email
├── domain_request.html # Domain approval request
├── admin_alert.html    # Admin notifications
└── test_email.html     # Test email template
```

### Base Template
```html
<!-- base.html -->
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body { font-family: Arial, sans-serif; }
        .header { background: #2196F3; color: white; padding: 20px; }
        .content { padding: 20px; }
        .footer { background: #f5f5f5; padding: 10px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>{{ title }}</h1>
    </div>
    <div class="content">
        {{ content }}
    </div>
    <div class="footer">
        <p>Architecture Decisions Application</p>
    </div>
</body>
</html>
```

### Welcome Email Template
```html
<!-- welcome.html -->
{% extends "base.html" %}
{% block content %}
<h2>Welcome to Architecture Decisions!</h2>
<p>Hello {{ user_name }},</p>
<p>Your account has been created successfully for {{ domain }}.</p>
<p>You can now start documenting your architecture decisions.</p>
<a href="{{ app_url }}" style="background: #2196F3; color: white; padding: 10px 20px; text-decoration: none;">
    Get Started
</a>
{% endblock %}
```

### Email Service Functions
```python
def send_email(to_email, subject, template_name, **template_vars):
    """Send an email using the specified template."""
    try:
        smtp_config = get_smtp_config()
        if not smtp_config:
            raise Exception("SMTP not configured")
        
        # Render template
        html_content = render_template(f'emails/{template_name}', **template_vars)
        
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = smtp_config['SMTP_USERNAME']
        msg['To'] = to_email
        
        # Attach HTML content
        html_part = MIMEText(html_content, 'html')
        msg.attach(html_part)
        
        # Send email
        with smtplib.SMTP(smtp_config['SMTP_SERVER'], smtp_config['SMTP_PORT']) as server:
            if smtp_config.get('SMTP_USE_TLS'):
                server.starttls()
            server.login(smtp_config['SMTP_USERNAME'], smtp_config['SMTP_PASSWORD'])
            server.send_message(msg)
            
        logger.info(f"Email sent successfully to {to_email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        return False
```

## Testing & Verification

### Admin Test Function

The application includes a built-in email test function accessible from the Super Admin panel:

#### Backend Implementation
```python
@app.route('/api/test-system-email', methods=['POST'])
@super_admin_required
def api_test_system_email():
    """Test system email functionality."""
    try:
        # Get super admin notification email
        test_email = SystemConfig.get(SystemConfig.KEY_SUPER_ADMIN_EMAIL, default='')
        if not test_email:
            return jsonify({
                'error': 'Super admin email not configured. Please set notification email in Email Configuration.'
            }), 400
        
        # Send test email
        success = send_email(
            to_email=test_email,
            subject='Architecture Decisions - System Email Test',
            template_name='test_email.html',
            test_time=datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
        )
        
        if success:
            return jsonify({'message': f'Test email sent successfully to {test_email}'})
        else:
            return jsonify({'error': 'Failed to send test email'}), 500
            
    except Exception as e:
        logger.error(f"Email test failed: {e}")
        return jsonify({'error': str(e)}), 500
```

#### Frontend Integration
```typescript
// email-config.component.ts
testSystemEmail() {
  this.isTestingEmail = true;
  
  this.http.post('/api/test-system-email', {}).subscribe({
    next: (response: any) => {
      this.snackBar.open(response.message, 'Close', { duration: 5000 });
    },
    error: (error) => {
      const message = error.error?.error || 'Failed to send test email';
      this.snackBar.open(message, 'Close', { duration: 5000 });
    },
    complete: () => {
      this.isTestingEmail = false;
    }
  });
}
```

### Manual Testing via CLI

For development and debugging, you can test email functionality directly:

```python
# test_email.py
from app import app, send_email

with app.app_context():
    result = send_email(
        to_email='test@example.com',
        subject='Test Email',
        template_name='test_email.html',
        test_time='Manual Test'
    )
    print(f"Email sent: {result}")
```

## Troubleshooting

### Common Issues

#### 1. Key Vault Access Denied
**Error**: `403 Forbidden` when accessing Key Vault

**Solution**:
```bash
# Verify managed identity has Key Vault access
az keyvault show-access-policy --name adr-keyvault-eu
```

#### 2. SMTP Authentication Failed
**Error**: `535 Authentication failed`

**Causes**:
- Incorrect username/password
- 2FA enabled without app password
- SMTP server blocking the connection

**Solutions**:
```bash
# For Gmail, create App Password:
# 1. Enable 2-Factor Authentication
# 2. Generate App Password
# 3. Use App Password instead of regular password

# Test SMTP credentials manually
az keyvault secret show --vault-name adr-keyvault-eu --name smtp-username
```

#### 3. Container Can't Access Key Vault
**Error**: `DefaultAzureCredential failed`

**Solution**:
```bash
# Recreate container with managed identity
az container create \
  --resource-group adr-resources-eu \
  --name adr-app-eu \
  --assign-identity \
  [other parameters...]
```

#### 4. Email Templates Not Found
**Error**: `TemplateNotFound: emails/template.html`

**Solution**:
Ensure email templates are included in the container:
```dockerfile
# In Dockerfile
COPY templates/ /app/templates/
```

### Debugging Steps

#### 1. Check SMTP Configuration
```python
# In Python console or temporary endpoint
smtp_config = get_smtp_config()
print(f"SMTP Config: {smtp_config}")
```

#### 2. Verify Key Vault Connection
```python
# Test Key Vault access
try:
    kv_client = KeyVaultClient()
    username, password = kv_client.get_smtp_credentials()
    print(f"Retrieved credentials: {bool(username)}, {bool(password)}")
except Exception as e:
    print(f"Key Vault error: {e}")
```

#### 3. Test SMTP Connection
```python
import smtplib

try:
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(username, password)
    print("SMTP connection successful")
    server.quit()
except Exception as e:
    print(f"SMTP connection failed: {e}")
```

### Monitoring and Logs

#### Application Logs
```bash
# View email-related logs
az container logs \
  --resource-group adr-resources-eu \
  --name adr-app-eu \
  | grep -i email
```

#### Key Vault Audit Logs
```bash
# Monitor Key Vault access
az monitor activity-log list \
  --resource-group adr-resources-eu \
  --caller adr-app-eu
```

## Security Best Practices

### 1. Credential Management
- **Never hardcode** SMTP credentials in source code
- Use **Azure Key Vault** for all sensitive configuration
- Rotate credentials regularly
- Use **managed identities** instead of service principals

### 2. Email Security
- Always use **TLS/SSL** for SMTP connections
- Validate email addresses before sending
- Implement **rate limiting** for email sending
- Log all email activities for audit

### 3. Template Security
- **Sanitize all user input** in email templates
- Use **parameterized templates** to prevent injection
- Validate template variables before rendering
- Store templates securely

### 4. Access Control
- Restrict email testing to **super admins only**
- Log all email configuration changes
- Monitor for unusual email sending patterns
- Implement **approval workflows** for template changes

---

*Last Updated: December 2024*