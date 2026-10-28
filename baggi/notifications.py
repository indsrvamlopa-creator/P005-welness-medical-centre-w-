import logging

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def notify_coach(subject, submission):
    """Email the coach a summary of a new website submission, if recipients are configured."""
    recipients = getattr(settings, 'COACH_NOTIFICATION_EMAILS', [])
    if not recipients:
        return

    lines = []
    for field in submission._meta.fields:
        if field.name in ('id', 'consent', 'status', 'coach_notes'):
            continue
        display = getattr(submission, f'get_{field.name}_display', None)
        value = display() if display else getattr(submission, field.name)
        if value not in (None, ''):
            lines.append(f'{field.verbose_name.capitalize()}: {value}')

    email_subject = f'[Website] {subject}'

    try:
        send_mail(
            email_subject,
            '\n'.join(lines) + '\n\nView all submissions in the website admin panel.',
            None,
            recipients,
        )
    except Exception:
        # A mail outage must never lose the visitor's saved submission.
        logger.exception('Could not send coach notification for %s', submission)
