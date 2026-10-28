"""Send Django email through Brevo's transactional email API.

Enabled in settings when BREVO_API_KEY is set. Uses only the standard library.
"""
import json
import logging
import urllib.error
import urllib.request
from email.utils import parseaddr

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)

API_URL = 'https://api.brevo.com/v3/smtp/email'


class BrevoEmailBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        sent = 0
        for message in email_messages:
            try:
                self._send(message)
                sent += 1
            except Exception:
                logger.exception('Brevo could not send "%s"', message.subject)
                if not self.fail_silently:
                    raise
        return sent

    def _send(self, message):
        name, address = parseaddr(message.from_email or settings.DEFAULT_FROM_EMAIL)
        payload = {
            'sender': {'name': name or settings.BREVO_SENDER_NAME, 'email': address},
            'to': [{'email': parseaddr(r)[1]} for r in message.to],
            'subject': message.subject,
            'textContent': message.body,
        }
        for content, mimetype in getattr(message, 'alternatives', []):
            if mimetype == 'text/html':
                payload['htmlContent'] = content
        if message.reply_to:
            payload['replyTo'] = {'email': parseaddr(message.reply_to[0])[1]}

        request = urllib.request.Request(
            API_URL,
            data=json.dumps(payload).encode('utf-8'),
            headers={
                'api-key': settings.BREVO_API_KEY,
                'content-type': 'application/json',
                'accept': 'application/json',
            },
            method='POST',
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                response.read()
        except urllib.error.HTTPError as error:
            raise RuntimeError(f'Brevo returned {error.code}: {error.read().decode(errors="replace")}') from error
