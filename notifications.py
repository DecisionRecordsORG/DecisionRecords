import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging

logger = logging.getLogger(__name__)


def send_email(email_config, to_email, subject, html_content, text_content=None):
    """Send an email using the provided SMTP configuration."""
    if not email_config or not email_config.enabled:
        logger.warning("Email not sent: Email configuration is missing or disabled")
        return False

    try:
        # Determine actual credentials to use
        smtp_username = email_config.smtp_username
        smtp_password = email_config.smtp_password
        
        # If config uses Key Vault placeholders, fetch from Key Vault
        if smtp_username == 'from-keyvault' or smtp_password == 'from-keyvault':
            from keyvault_client import keyvault_client
            kv_username, kv_password = keyvault_client.get_smtp_credentials()
            
            if not kv_username or not kv_password:
                logger.error("SMTP credentials not available in Key Vault")
                return False
                
            smtp_username = kv_username
            smtp_password = kv_password
            logger.info("Using SMTP credentials from Key Vault")

        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f"{email_config.from_name} <{email_config.from_email}>"
        msg['To'] = to_email

        # Add plain text version if provided
        if text_content:
            msg.attach(MIMEText(text_content, 'plain'))

        # Add HTML version
        msg.attach(MIMEText(html_content, 'html'))

        # Connect and send
        if email_config.use_tls:
            server = smtplib.SMTP(email_config.smtp_server, email_config.smtp_port)
            server.starttls()
        else:
            server = smtplib.SMTP_SSL(email_config.smtp_server, email_config.smtp_port)

        server.login(smtp_username, smtp_password)
        server.sendmail(email_config.from_email, to_email, msg.as_string())
        server.quit()

        logger.info(f"Email sent successfully to {to_email}")
        return True

    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {str(e)}")
        return False


def notify_subscribers_new_decision(db, decision, email_config):
    """Notify subscribers about a new architecture decision."""
    from models import User, Subscription

    if not email_config or not email_config.enabled:
        return

    # Get all subscribers in the same domain who want to be notified on create
    subscribers = db.session.query(User).join(Subscription).filter(
        User.sso_domain == decision.domain,
        Subscription.notify_on_create == True
    ).all()

    subject = f"[ADR] New Architecture Decision: {decision.title}"

    for subscriber in subscribers:
        # Don't notify the creator
        if decision.created_by_id and subscriber.id == decision.created_by_id:
            continue

        html_content = f"""
        <html>
        <body>
            <h2>New Architecture Decision Created</h2>
            <p><strong>ADR-{decision.id}: {decision.title}</strong></p>
            <p><strong>Status:</strong> {decision.status.capitalize()}</p>
            <p><strong>Created by:</strong> {decision.creator.name if decision.creator else 'Unknown'}</p>

            <h3>Context</h3>
            <p>{decision.context}</p>

            <h3>Decision</h3>
            <p>{decision.decision}</p>

            <h3>Consequences</h3>
            <p>{decision.consequences}</p>

            <hr>
            <p><small>You are receiving this because you subscribed to new decision notifications.</small></p>
        </body>
        </html>
        """

        text_content = f"""
New Architecture Decision Created

ADR-{decision.id}: {decision.title}
Status: {decision.status.capitalize()}
Created by: {decision.creator.name if decision.creator else 'Unknown'}

Context:
{decision.context}

Decision:
{decision.decision}

Consequences:
{decision.consequences}

---
You are receiving this because you subscribed to new decision notifications.
        """

        send_email(email_config, subscriber.email, subject, html_content, text_content)


def notify_subscribers_decision_updated(db, decision, email_config, change_reason=None, status_changed=False):
    """Notify subscribers about an updated architecture decision."""
    from models import User, Subscription

    if not email_config or not email_config.enabled:
        return

    # Build filter based on notification type
    if status_changed:
        subscribers = db.session.query(User).join(Subscription).filter(
            User.sso_domain == decision.domain,
            (Subscription.notify_on_update == True) | (Subscription.notify_on_status_change == True)
        ).all()
    else:
        subscribers = db.session.query(User).join(Subscription).filter(
            User.sso_domain == decision.domain,
            Subscription.notify_on_update == True
        ).all()

    subject = f"[ADR] Updated: {decision.title}"
    if status_changed:
        subject = f"[ADR] Status Changed: {decision.title} - Now {decision.status.capitalize()}"

    for subscriber in subscribers:
        # Don't notify the person who made the update
        if decision.updated_by_id and subscriber.id == decision.updated_by_id:
            continue

        html_content = f"""
        <html>
        <body>
            <h2>Architecture Decision Updated</h2>
            <p><strong>ADR-{decision.id}: {decision.title}</strong></p>
            <p><strong>Status:</strong> {decision.status.capitalize()}</p>
            <p><strong>Updated by:</strong> {decision.updated_by.name if decision.updated_by else 'Unknown'}</p>
            {f'<p><strong>Change reason:</strong> {change_reason}</p>' if change_reason else ''}

            <h3>Context</h3>
            <p>{decision.context}</p>

            <h3>Decision</h3>
            <p>{decision.decision}</p>

            <h3>Consequences</h3>
            <p>{decision.consequences}</p>

            <hr>
            <p><small>You are receiving this because you subscribed to decision update notifications.</small></p>
        </body>
        </html>
        """

        text_content = f"""
Architecture Decision Updated

ADR-{decision.id}: {decision.title}
Status: {decision.status.capitalize()}
Updated by: {decision.updated_by.name if decision.updated_by else 'Unknown'}
{f'Change reason: {change_reason}' if change_reason else ''}

Context:
{decision.context}

Decision:
{decision.decision}

Consequences:
{decision.consequences}

---
You are receiving this because you subscribed to decision update notifications.
        """

        send_email(email_config, subscriber.email, subject, html_content, text_content)


def send_setup_token_email(email_config, user_name, user_email, setup_url, expires_in_hours, app_name="Architecture Decisions"):
    """Send a setup token email to a user so they can set up their login credentials."""
    subject = f"Set Up Your {app_name} Account"

    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #3f51b5;">Welcome to {app_name}!</h2>

            <p>Hi {user_name},</p>

            <p>Your account has been approved! Please click the button below to set up your login credentials (passkey or password).</p>

            <div style="text-align: center; margin: 30px 0;">
                <a href="{setup_url}"
                   style="display: inline-block; background-color: #3f51b5; color: white; padding: 14px 28px;
                          text-decoration: none; border-radius: 6px; font-weight: bold;">
                    Set Up Your Account
                </a>
            </div>

            <p style="color: #666; font-size: 14px;">
                <strong>Important:</strong> This link will expire in <strong>{expires_in_hours} hours</strong>.
            </p>

            <p style="color: #666; font-size: 14px;">
                If the button doesn't work, copy and paste this link into your browser:
            </p>
            <p style="background-color: #f5f5f5; padding: 10px; border-radius: 4px; word-break: break-all; font-size: 13px;">
                {setup_url}
            </p>

            <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">

            <p style="color: #999; font-size: 12px;">
                If you didn't request access to {app_name}, you can safely ignore this email.
            </p>
        </div>
    </body>
    </html>
    """

    text_content = f"""
Welcome to {app_name}!

Hi {user_name},

Your account has been approved! Please use the link below to set up your login credentials (passkey or password).

Set Up Your Account:
{setup_url}

Important: This link will expire in {expires_in_hours} hours.

---
If you didn't request access to {app_name}, you can safely ignore this email.
    """

    return send_email(email_config, user_email, subject, html_content, text_content)


def send_account_setup_email(email_config, user_name, user_email, setup_url, expires_in_hours, tenant_name=None, app_name="Architecture Decisions"):
    """Send an email to a new user to complete their account setup (for auto-approved signups)."""
    subject = f"Complete Your {app_name} Account Setup"

    org_text = f" for {tenant_name}" if tenant_name else ""

    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #3f51b5;">Complete Your Account Setup</h2>

            <p>Hi {user_name},</p>

            <p>Your account{org_text} has been created! Please click the button below to set up your login credentials (passkey or password).</p>

            <div style="text-align: center; margin: 30px 0;">
                <a href="{setup_url}"
                   style="display: inline-block; background-color: #3f51b5; color: white; padding: 14px 28px;
                          text-decoration: none; border-radius: 6px; font-weight: bold;">
                    Complete Account Setup
                </a>
            </div>

            <p style="color: #666; font-size: 14px;">
                <strong>Important:</strong> This link will expire in <strong>{expires_in_hours} hours</strong>.
            </p>

            <p style="color: #666; font-size: 14px;">
                If the button doesn't work, copy and paste this link into your browser:
            </p>
            <p style="background-color: #f5f5f5; padding: 10px; border-radius: 4px; word-break: break-all; font-size: 13px;">
                {setup_url}
            </p>

            <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">

            <p style="color: #999; font-size: 12px;">
                If you didn't sign up for {app_name}, you can safely ignore this email.
            </p>
        </div>
    </body>
    </html>
    """

    text_content = f"""
Complete Your Account Setup

Hi {user_name},

Your account{org_text} has been created! Please use the link below to set up your login credentials (passkey or password).

Complete Account Setup:
{setup_url}

Important: This link will expire in {expires_in_hours} hours.

---
If you didn't sign up for {app_name}, you can safely ignore this email.
    """

    return send_email(email_config, user_email, subject, html_content, text_content)


def send_account_recovery_email(email_config, user_name, user_email, recovery_url, expires_in_hours, app_name="Architecture Decisions"):
    """Send an account recovery email to a user so they can reset their credentials."""
    subject = f"Reset Your {app_name} Credentials"

    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #3f51b5;">Account Recovery</h2>

            <p>Hi {user_name},</p>

            <p>We received a request to reset your login credentials for {app_name}. Click the button below to set up a new passkey or password.</p>

            <div style="text-align: center; margin: 30px 0;">
                <a href="{recovery_url}"
                   style="display: inline-block; background-color: #3f51b5; color: white; padding: 14px 28px;
                          text-decoration: none; border-radius: 6px; font-weight: bold;">
                    Reset My Credentials
                </a>
            </div>

            <p style="color: #666; font-size: 14px;">
                <strong>Important:</strong> This link will expire in <strong>{expires_in_hours} hours</strong>.
            </p>

            <p style="color: #666; font-size: 14px;">
                If the button doesn't work, copy and paste this link into your browser:
            </p>
            <p style="background-color: #f5f5f5; padding: 10px; border-radius: 4px; word-break: break-all; font-size: 13px;">
                {recovery_url}
            </p>

            <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">

            <p style="color: #999; font-size: 12px;">
                If you didn't request this password reset, you can safely ignore this email. Your current credentials will remain unchanged.
            </p>
        </div>
    </body>
    </html>
    """

    text_content = f"""
Account Recovery - {app_name}

Hi {user_name},

We received a request to reset your login credentials for {app_name}. Use the link below to set up a new passkey or password.

Reset My Credentials:
{recovery_url}

Important: This link will expire in {expires_in_hours} hours.

---
If you didn't request this password reset, you can safely ignore this email. Your current credentials will remain unchanged.
    """

    return send_email(email_config, user_email, subject, html_content, text_content)
