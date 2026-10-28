"""Sidebar menu and dashboard data for the custom admin layout."""
from datetime import timedelta

from django import template
from django.urls import reverse
from django.utils import timezone

from ..models import AdminPageVisit, CommunityEvent, CommunityInterest, Review, WellnessConsultation

register = template.Library()

# (group title, [model object_name, ...]); models not listed fall into "More".
SIDEBAR_GROUPS = [
    ('Enquiries', ['ServiceBooking', 'WellnessConsultation', 'CommunityInterest', 'EventRegistration']),
    ('Website', ['Service', 'CommunityEvent', 'Review', 'SuccessStory', 'AboutPhoto']),
    ('Settings', ['SiteSettings', 'User', 'Group']),
]

ICONS = {
    'ServiceBooking': 'inbox',
    'WellnessConsultation': 'calendar-check',
    'CommunityInterest': 'mail',
    'EventRegistration': 'ticket',
    'Service': 'sparkle',
    'CommunityEvent': 'calendar',
    'Review': 'star',
    'SuccessStory': 'quote',
    'AboutPhoto': 'image',
    'SiteSettings': 'sliders',
    'User': 'user',
    'Group': 'users',
}


def _new_since_visit(user, page, source):
    """Submissions from one website form that arrived since this admin last opened its list."""
    items = WellnessConsultation.objects.filter(source=source)
    last_visit = AdminPageVisit.objects.filter(user=user, page=page).first()
    if last_visit:
        items = items.filter(submitted_at__gt=last_visit.visited_at)
    return items.count()


def _badges(user):
    """Counts of items waiting for the coach, keyed by model object_name."""
    badges = {}
    if user.has_perm('baggi.view_wellnessconsultation'):
        badges['WellnessConsultation'] = _new_since_visit(user, 'wellnessconsultation', 'consultation')
    if user.has_perm('baggi.view_servicebooking'):
        badges['ServiceBooking'] = _new_since_visit(user, 'servicebooking', 'service')
    if user.has_perm('baggi.view_review'):
        badges['Review'] = Review.objects.filter(is_approved=False).count()
    return badges


@register.inclusion_tag('admin/_cw_sidebar.html', takes_context=True)
def cw_sidebar(context):
    request = context['request']
    badges = _badges(request.user)
    models = {}
    for app in context.get('available_apps', []):
        for model in app['models']:
            models[model['object_name']] = model

    def item(name):
        model = models.pop(name)
        url = model.get('admin_url') or ''
        return {
            'name': model['name'],
            'url': url,
            'icon': ICONS.get(name, 'dot'),
            'active': bool(url) and request.path.startswith(url),
            'badge': badges.get(name, 0),
        }

    groups = []
    for title, names in SIDEBAR_GROUPS:
        items = [item(name) for name in names if name in models]
        if items:
            groups.append({'title': title, 'items': items})
    if models:
        groups.append({'title': 'More', 'items': [item(name) for name in list(models)]})

    index_url = reverse('admin:index')
    return {
        'groups': groups,
        'dashboard_url': index_url,
        'dashboard_active': request.path == index_url,
        'site_url': context.get('site_url') or '/',
    }


@register.simple_tag(takes_context=True)
def cw_dashboard(context):
    """Numbers and short lists for the admin dashboard, limited to what the user may view."""
    user = context['request'].user
    now = timezone.now()
    data = {'stats': [], 'consultations': None, 'events': None}

    def admin_url(model_name, query=''):
        return reverse(f'admin:baggi_{model_name}_changelist') + query

    if user.has_perm('baggi.view_wellnessconsultation'):
        data['stats'].append({
            'label': 'New consultation bookings',
            'value': WellnessConsultation.objects.filter(status='new', source='consultation').count(),
            'url': admin_url('wellnessconsultation', '?status__exact=new'),
            'icon': 'calendar-check',
            'tone': 'gold',
        })
        data['consultations'] = WellnessConsultation.objects.select_related('service')[:5]
        data['consultations_url'] = admin_url('wellnessconsultation')
    if user.has_perm('baggi.view_servicebooking'):
        data['stats'].insert(0, {
            'label': 'New service bookings',
            'value': WellnessConsultation.objects.filter(status='new', source='service').count(),
            'url': admin_url('servicebooking', '?status__exact=new'),
            'icon': 'inbox',
            'tone': 'blue',
        })
    if user.has_perm('baggi.view_communityevent'):
        upcoming = CommunityEvent.objects.upcoming().order_by('starts_at')
        data['stats'].append({
            'label': 'Upcoming events',
            'value': upcoming.count(),
            'url': admin_url('communityevent'),
            'icon': 'calendar',
            'tone': 'blue',
        })
        data['events'] = upcoming[:4]
        data['events_url'] = admin_url('communityevent')
    if user.has_perm('baggi.view_review'):
        data['stats'].append({
            'label': 'Reviews to approve',
            'value': Review.objects.filter(is_approved=False).count(),
            'url': admin_url('review', '?is_approved__exact=0'),
            'icon': 'star',
            'tone': 'gold',
        })
    if user.has_perm('baggi.view_communityinterest'):
        data['stats'].append({
            'label': 'Enquiries this week',
            'value': CommunityInterest.objects.filter(submitted_at__gte=now - timedelta(days=7)).count(),
            'url': admin_url('communityinterest'),
            'icon': 'mail',
            'tone': 'blue',
        })

    hour = timezone.localtime(now).hour
    data['greeting'] = 'Good morning' if hour < 12 else 'Good afternoon' if hour < 17 else 'Good evening'
    return data


@register.inclusion_tag('admin/_cw_icon.html')
def cw_icon(name):
    return {'name': name}
