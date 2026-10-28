import json
import logging
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def notify_coach(subject, submission):
    """Email the coach a summary of a new website submission, if recipients are configured."""
    recipients = getattr(settings, 'COACH_NOTIFICATION_EMAILS', [])
    if not recipients:
        return

    rows = []
    for field in submission._meta.fields:
        if field.name in ('id', 'status', 'coach_notes'):
            continue
        display = getattr(submission, f'get_{field.name}_display', None)
        value = display() if display else getattr(submission, field.name)
        if value not in (None, ''):
            if isinstance(value, bool):
                value = 'Yes' if value else 'No'
            rows.append({
                'label': field.verbose_name.capitalize(),
                'value': value,
            })

    email_subject = f'[Website] {subject}'
    brand_name = getattr(settings, 'BREVO_SENDER_NAME', "Geetha's Wellness Consultancy")
    body = '\n'.join(f"{row['label']}: {row['value']}" for row in rows)
    html_body = render_to_string('baggi/emails/submission_notification.html', {
        'brand_name': brand_name,
        'subject': subject,
        'rows': rows,
    })

    try:
        api_key = getattr(settings, 'BREVO_API_KEY', '')
        if api_key:
            sender_email = getattr(settings, 'BREVO_SENDER_EMAIL', '')
            if not sender_email:
                raise ValueError('BREVO_SENDER_EMAIL must be configured when BREVO_API_KEY is set.')

            payload = {
                'sender': {
                    'name': getattr(settings, 'BREVO_SENDER_NAME', "Geetha's Wellness Consultancy"),
                    'email': sender_email,
                },
                'to': [{'email': recipient} for recipient in recipients],
                'subject': email_subject,
                'textContent': body,
                'htmlContent': html_body,
            }
            request = Request(
                'https://api.brevo.com/v3/smtp/email',
                data=json.dumps(payload).encode('utf-8'),
                headers={
                    'accept': 'application/json',
                    'api-key': api_key,
                    'content-type': 'application/json',
                },
                method='POST',
            )
            with urlopen(request, timeout=10):
                pass
            return

        send_mail(
            email_subject,
            body,
            None,
            recipients,
            html_message=html_body,
        )
    except Exception:
        # A mail outage must never lose the visitor's saved submission.
        logger.exception('Could not send coach notification for %s', submission)
