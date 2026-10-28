import re
from pathlib import Path

from django.conf import settings
from django.db import DatabaseError

STATIC_DIR = Path(__file__).resolve().parent / 'static' / 'baggi'


def _asset_version():
    """Changes whenever the site CSS or JS changes, so browsers never use a stale copy."""
    try:
        return str(int(max((STATIC_DIR / name).stat().st_mtime for name in ('styles.css', 'site.js', 'admin.css', 'admin.js'))))
    except OSError:
        return '1'


def _site_settings():
    from .models import SiteSettings

    try:
        return SiteSettings.load()
    except DatabaseError:  # e.g. before migrations have run
        return SiteSettings()


def site_settings(request):
    site = _site_settings()
    # The admin setting wins; the settings.py value is a fallback.
    raw_number = site.whatsapp_number or getattr(settings, 'COMMUNITY_WHATSAPP_NUMBER', '')
    return {
        'member_disclosure': getattr(settings, 'MEMBER_DISCLOSURE', ''),
        'asset_version': _asset_version(),
        'site': site,
        'whatsapp_number': re.sub(r'[^0-9]', '', raw_number),
        'whatsapp_message': site.whatsapp_message or getattr(settings, 'WHATSAPP_GREETING', ''),
    }
