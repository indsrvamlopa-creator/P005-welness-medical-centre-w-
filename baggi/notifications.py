import logging
import re

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

logger = logging.getLogger(__name__)

# Fields that are internal bookkeeping, not something the visitor told us.
HIDDEN_FIELDS = {'id', 'consent', 'status', 'coach_notes', 'source', 'is_approved', 'consent_to_publish', 'website'}
# Clearer wording for some field names in the email.
LABELS = {
    'submitted_at': 'Received',
    'area_city': 'Area / city',
    'service': 'Service',
    'attendees': 'People attending',
    'preferred_at': 'Preferred date & time',
    'review': 'Their review',
    'rating': 'Rating',
}
# Shown as contact buttons at the top instead of in the details table.
CONTACT_FIELDS = {'full_name', 'mobile_number', 'email'}


def _kind(submission):
    """What this submission is, in plain words, plus the coach's next step."""
    name = submission.full_name
    model = submission._meta.model_name
    if model == 'wellnessconsultation' and getattr(submission, 'source', '') == 'service':
        service = submission.service.title if submission.service else 'a service'
        return {
            'label': 'Service booking', 'colour': '#d3b76f', 'admin_model': 'servicebooking',
            'headline': f'New booking: {service}',
            'summary': f'{name} booked “{service}” using “Book this” on your website.',
            'next_step': 'Call or WhatsApp them to confirm a time, then set the booking status to “Contacted” in the admin.',
        }
    if model == 'wellnessconsultation':
        return {
            'label': 'Free consultation', 'colour': '#7fb2e6', 'admin_model': 'wellnessconsultation',
            'headline': 'New free consultation request',
            'summary': f'{name} asked for a free wellness consultation through your website.',
            'next_step': 'Contact them using their preferred method to arrange the consultation.',
        }
    if model == 'eventregistration':
        event = submission.event
        mode = 'online' if event.is_online else 'in person'
        return {
            'label': 'Event registration', 'colour': '#8fd6b4', 'admin_model': 'eventregistration',
            'headline': f'New registration: {event.title}',
            'summary': (
                f'{name} registered for “{event.title}” ({mode}) on '
                f'{timezone.localtime(event.starts_at):%a %d %b %Y, %I:%M %p}.'
            ),
            'next_step': (
                'Send them the joining link before the event.' if event.is_online
                else 'Share the venue details and confirm their place.'
            ),
        }
    if model == 'review':
        return {
            'label': 'New review', 'colour': '#f0c36a', 'admin_model': 'review',
            'headline': f'{name} left a {submission.rating}-star review',
            'summary': 'A new review is waiting for your approval. It is not visible on the website yet.',
            'next_step': 'Open it in the admin and tick “Approved” to publish it, or delete it.',
        }
    return {
        'label': 'Community enquiry', 'colour': '#c9a7f0', 'admin_model': 'communityinterest',
        'headline': 'New community enquiry',
        'summary': f'{name} sent an enquiry through the “Join the community” form.',
        'next_step': 'Reply using their preferred contact method.',
    }


def _format(value):
    if hasattr(value, 'tzinfo') and hasattr(value, 'hour'):
        return f'{timezone.localtime(value):%d %b %Y, %I:%M %p}'
    if value is True:
        return 'Yes'
    if value is False:
        return 'No'
    return str(value)


def _details(submission):
    rows = []
    for field in submission._meta.fields:
        if field.name in HIDDEN_FIELDS | CONTACT_FIELDS or field.name.endswith('_photo'):
            continue
        display = getattr(submission, f'get_{field.name}_display', None)
        value = display() if display else getattr(submission, field.name)
        if value in (None, ''):
            continue
        if field.name == 'rating':
            value = f'{"★" * submission.rating} ({submission.rating} out of 5)'
        elif field.name == 'event':
            value = f'{value.title}, {timezone.localtime(value.starts_at):%a %d %b %Y, %I:%M %p}'
        label = LABELS.get(field.name) or field.verbose_name[:1].upper() + field.verbose_name[1:]
        rows.append((label, _format(value)))
    return rows


def _international(mobile):
    """Digits for tel:/WhatsApp links; a bare 10-digit number is treated as Indian (+91)."""
    digits = re.sub(r'[^0-9]', '', mobile or '').lstrip('0') if mobile else ''
    return f'91{digits}' if len(digits) == 10 else digits


def _admin_link(kind, submission):
    base = getattr(settings, 'SITE_URL', '').rstrip('/')
    try:
        path = reverse(f'admin:baggi_{kind["admin_model"]}_change', args=[submission.pk])
    except NoReverseMatch:
        path = reverse('admin:index')
    return f'{base}{path}'


def notify_coach(subject, submission):
    """Email the coach a clear summary of a new website submission, if recipients are configured."""
    recipients = getattr(settings, 'COACH_NOTIFICATION_EMAILS', [])
    if not recipients:
        return

    try:
        kind = _kind(submission)
        mobile = getattr(submission, 'mobile_number', '')
        context = {
            'kind': kind,
            'name': submission.full_name,
            'mobile': mobile,
            'mobile_digits': _international(mobile),
            'email': getattr(submission, 'email', ''),
            'details': _details(submission),
            'admin_link': _admin_link(kind, submission),
            'site_name': getattr(settings, 'BREVO_SENDER_NAME', 'Your website'),
        }
        text = render_to_string('baggi/emails/notification.txt', context)
        html = render_to_string('baggi/emails/notification.html', context)
        visitor_email = context['email']
        message = EmailMultiAlternatives(
            f'[Website] {subject} — {submission.full_name}',
            text,
            None,
            recipients,
            # Replying to the notification answers the visitor directly.
            reply_to=[visitor_email] if visitor_email else None,
        )
        message.attach_alternative(html, 'text/html')
        message.send()
    except Exception:
        # A mail outage must never lose the visitor's saved submission.
        logger.exception('Could not send coach notification for %s', submission)
