"""
WSGI config for welfare project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.1/howto/deployment/wsgi/
"""

import os

import django
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'welfare.settings')


def _prepare_render():
    """On Render, set up the database, static files and admin login before serving.

    This works whatever build/start commands the Render dashboard has, and is needed
    anyway on the free plan, where the SQLite database starts empty after a deploy.
    """
    from django.contrib.auth import get_user_model
    from django.core.management import call_command

    call_command('migrate', interactive=False, verbosity=1)
    call_command('collectstatic', interactive=False, verbosity=0)

    username = os.environ.get('DJANGO_SUPERUSER_USERNAME')
    if username and os.environ.get('DJANGO_SUPERUSER_PASSWORD'):
        User = get_user_model()
        if not User.objects.filter(username=username).exists():
            call_command('createsuperuser', interactive=False, verbosity=1)


if os.environ.get('RENDER'):
    django.setup()
    _prepare_render()

application = get_wsgi_application()
