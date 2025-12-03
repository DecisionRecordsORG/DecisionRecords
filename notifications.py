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

        server.login(email_config.smtp_username, email_config.smtp_password)
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
