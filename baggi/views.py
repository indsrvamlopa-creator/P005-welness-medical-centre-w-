from django.contrib import messages
from django.templatetags.static import static
from django.core.files.storage import default_storage
from django.core.paginator import Paginator
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from django.db.models import Avg, Count

from .forms import (
    CommunityInterestForm,
    EventRegistrationForm,
    ReviewForm,
    WellnessConsultationForm,
)
from .models import AboutPhoto, CommunityEvent, Review, Service, SuccessStory
from .notifications import notify_coach

PAST_EVENTS_PER_PAGE = 3
# Reviews visible before the visitor clicks “Show more reviews”.
REVIEWS_INITIAL = 4


def event_registration_form(event_pk, open_events, data=None):
    """A registration form fixed to one event, with field ids unique to its card."""
    return EventRegistrationForm(
        data,
        events=open_events,
        initial={'event': event_pk},
        hide_event=True,
        auto_id=f'id_event{event_pk}_%s',
    )


# Shown in the About slideshow until the coach uploads their own photos.
DEFAULT_ABOUT_PHOTOS = [
    ('baggi/media/about/exercise-1.jpg', 'A woman holding a yoga pose by the sea at sunset'),
    ('baggi/media/about/exercise-2.jpg', 'Lifting a barbell in the gym'),
    ('baggi/media/about/exercise-3.jpg', 'A coach guiding a client through push-ups'),
    ('baggi/media/about/exercise-4.jpg', 'A group exercise class on mats'),
    ('baggi/media/about/exercise-5.jpg', 'A battle rope workout'),
    ('baggi/media/about/exercise-6.jpg', 'A woman doing sit-ups on a mat'),
]


def about_photos():
    """(url, alt) pairs for the About slideshow."""
    # A file can disappear (e.g. Render's free disk is wiped on redeploy); never show a broken image.
    uploaded = [
        (photo.image.url, photo.alt_text)
        for photo in AboutPhoto.objects.filter(is_published=True)
        if photo.image and default_storage.exists(photo.image.name)
    ]
    return uploaded or [(static(path), alt) for path, alt in DEFAULT_ABOUT_PHOTOS]


@require_http_methods(['GET', 'HEAD', 'POST'])
def home(request):
    events = list(CommunityEvent.objects.upcoming())
    open_events = CommunityEvent.objects.filter(
        pk__in=[event.pk for event in events if event.registration_status == 'open'],
    )
    # get_page() falls back to the first/last page for missing or out-of-range numbers.
    past_page = Paginator(
        CommunityEvent.objects.filter(
            is_published=True,
            starts_at__lt=timezone.now(),
        ).order_by('-starts_at', '-pk'),
        PAST_EVENTS_PER_PAGE,
    ).get_page(request.GET.get('past_page'))
    services = Service.objects.filter(is_published=True)
    # Open the form on the card the visitor came for (?event=<id>) or just submitted.
    expanded_event_pk = request.GET.get('event', '')
    bound_event_form = None
    interest_form = CommunityInterestForm()
    review_form = ReviewForm()
    review_form_open = False
    selected_service = services.filter(slug=request.GET.get('service', '')).first()
    consultation_form = WellnessConsultationForm(
        initial={'service': selected_service} if selected_service else None,
    )
    # The "Book this" popup on the service cards; prefixed so it never clashes with the section form.
    book_form = WellnessConsultationForm(prefix='book')
    book_form_open = False

    if request.method == 'POST':
        form_type = request.POST.get('form_type')
        if form_type == 'consultation':
            consultation_form = WellnessConsultationForm(request.POST)
            if consultation_form.is_valid():
                consultation = consultation_form.save()
                notify_coach('New free consultation request', consultation)
                messages.success(
                    request,
                    'Thank you. Your free wellness consultation request has been received. '
                    'The coach will contact you to confirm a time.',
                )
                return redirect(f'{reverse("home")}#consultation')
            messages.error(request, 'Please check the consultation form and try again.')
        elif form_type == 'book':
            book_form = WellnessConsultationForm(request.POST, prefix='book')
            if book_form.is_valid():
                booking = book_form.save(commit=False)
                booking.source = 'service'
                booking.save()
                notify_coach('New service booking request', booking)
                service_name = booking.service.title if booking.service else 'your consultation'
                messages.success(
                    request,
                    f'Thank you. Your booking request for “{service_name}” has been received. '
                    'The coach will contact you to confirm a time.',
                )
                return redirect(f'{reverse("home")}#services')
            book_form_open = True
            messages.error(request, 'Please check the booking form and try again.')
        elif form_type == 'event':
            expanded_event_pk = request.POST.get('event', '')
            if not open_events.filter(pk=expanded_event_pk or None).exists():
                messages.error(request, 'Sorry, registration for this event is not open.')
            else:
                bound_event_form = event_registration_form(
                    expanded_event_pk, open_events, data=request.POST,
                )
                if bound_event_form.is_valid():
                    registration = bound_event_form.save()
                    notify_coach('New event registration', registration)
                    messages.success(
                        request,
                        f'Thank you. Your registration for “{registration.event.title}” has been received.',
                    )
                    return redirect(f'{reverse("home")}#event-{registration.event.pk}')
                messages.error(request, 'Please check the event registration form and try again.')
        elif form_type == 'review':
            review_form = ReviewForm(request.POST)
            if review_form.is_valid():
                review = review_form.save()
                notify_coach('New review waiting for approval', review)
                messages.success(
                    request,
                    'Thank you for your review! It will appear on the website once it has been approved.',
                )
                return redirect(f'{reverse("home")}#reviews')
            review_form_open = True
            messages.error(request, 'Please check the review form and try again.')
        elif form_type == 'community':
            interest_form = CommunityInterestForm(request.POST)
            if interest_form.is_valid():
                interest = interest_form.save()
                notify_coach('New community enquiry', interest)
                messages.success(
                    request,
                    'Thank you for your interest. Your community enquiry has been received.',
                )
                return redirect(f'{reverse("home")}#join')
            messages.error(request, 'Please check the community enquiry form and try again.')
        else:
            messages.error(request, 'We could not identify that form. Please try again.')

    # Each open upcoming event card carries its own registration form.
    for event in events:
        event.form_expanded = str(event.pk) == str(expanded_event_pk)
        if event.registration_status != 'open':
            event.registration_form = None
        elif bound_event_form is not None and event.form_expanded:
            event.registration_form = bound_event_form
        else:
            event.registration_form = event_registration_form(event.pk, open_events)

    approved_reviews = list(Review.objects.filter(is_approved=True).select_related('service'))

    return render(request, 'baggi/home.html', {
        'about_photos': about_photos(),
        'services': services,
        'success_story': SuccessStory.objects.filter(
            is_published=True,
            client_consent=True,
        ).first(),
        'consultation_form': consultation_form,
        'book_form': book_form,
        'book_form_open': book_form_open,
        'reviews': approved_reviews,
        'reviews_initial': REVIEWS_INITIAL,
        'reviews_hidden_count': max(len(approved_reviews) - REVIEWS_INITIAL, 0),
        'review_stats': Review.objects.filter(is_approved=True).aggregate(
            average=Avg('rating'),
            count=Count('id'),
        ),
        'review_form': review_form,
        'review_form_open': review_form_open,
        'events': events,
        'past_events': past_page.object_list,
        'past_page': past_page,
        'past_page_range': past_page.paginator.get_elided_page_range(past_page.number, on_each_side=1, on_ends=1),
        'interest_form': interest_form,
    })


@require_http_methods(['GET', 'HEAD'])
def privacy(request):
    return render(request, 'baggi/privacy.html')
