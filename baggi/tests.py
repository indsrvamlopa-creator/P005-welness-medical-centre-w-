import io
import json
import shutil
import tempfile
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from django.contrib.auth import get_user_model
from django.core import mail

from .models import (
    AboutPhoto,
    CommunityEvent,
    CommunityInterest,
    EventRegistration,
    Review,
    Service,
    SiteSettings,
    SuccessStory,
    WellnessConsultation,
)


class CommunityWebsiteTests(TestCase):
    def test_homepage_has_coaching_sections_and_member_disclosure(self):
        response = self.client.get('/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Better days')
        self.assertContains(response, 'About us')
        self.assertNotContains(response, 'associated with Herbalife')
        for offer in ('Personalised wellness guidance', 'Weight management support', 'Healthy lifestyle coaching',
                      'Nutrition education', 'Fitness challenges', 'Wellness assessments'):
            self.assertContains(response, offer)
        self.assertNotContains(response, 'Herbalife nutrition products')
        self.assertNotContains(response, 'class="about-badge"')
        self.assertContains(response, 'Our services')
        self.assertContains(response, 'Free wellness consultation')
        self.assertContains(response, 'Upcoming gatherings')
        self.assertContains(response, 'Join the community')
        self.assertContains(response, 'Privacy notice')
        self.assertContains(response, 'Independent Herbalife Member')
        self.assertContains(response, 'Check your BMI')
        self.assertContains(response, 'baggi/media/hero-workout.mp4')
        self.assertContains(response, 'id="hero-video-toggle"')

    def test_privacy_notice_page_is_available(self):
        response = self.client.get('/privacy/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Who can access it')
        self.assertContains(response, 'How long we keep it')

    def test_admin_enquiry_area_requires_authentication(self):
        response = self.client.get('/admin/baggi/communityinterest/')

        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/login/', response.url)

    def test_whatsapp_link_is_not_shown_without_an_approved_number(self):
        response = self.client.get('/')

        self.assertNotContains(response, 'https://wa.me/')
        # The floating chat button still shows, pointing at the enquiry form.
        self.assertContains(response, '<a class="whatsapp-float" href="/#join"')

    @override_settings(COMMUNITY_WHATSAPP_NUMBER='+1 (555) 123-4567')
    def test_whatsapp_click_to_chat_uses_the_configured_number(self):
        response = self.client.get('/')

        self.assertContains(response, 'https://wa.me/15551234567?text=')
        self.assertContains(response, 'whatsapp-float')

    def test_published_events_are_listed_past_as_completed_and_drafts_hidden(self):
        upcoming = CommunityEvent.objects.create(
            title='Community walk',
            description='A relaxed walk together.',
            starts_at=timezone.now() + timedelta(days=7),
            venue='Riverside Park',
            is_published=True,
        )
        past = CommunityEvent.objects.create(
            title='Past gathering',
            description='Already happened.',
            starts_at=timezone.now() - timedelta(days=1),
            is_published=True,
        )
        CommunityEvent.objects.create(
            title='Draft gathering',
            description='Not announced.',
            starts_at=timezone.now() + timedelta(days=14),
            is_published=False,
        )

        response = self.client.get('/')

        self.assertContains(response, upcoming.title)
        self.assertContains(response, 'Riverside Park')
        self.assertContains(response, 'Recent events')
        self.assertContains(response, 'Past gathering')
        self.assertContains(response, 'Completed')
        self.assertNotContains(response, f'name="event" value="{past.pk}"')
        self.assertNotContains(response, 'Draft gathering')
        self.assertEqual(
            [event.registration_form is not None for event in response.context['events']],
            [True],
        )

    def test_valid_event_registration_is_saved(self):
        event = CommunityEvent.objects.create(
            title='Community walk',
            description='A relaxed walk together.',
            starts_at=timezone.now() + timedelta(days=7),
            is_published=True,
        )
        response = self.client.post(
            '/#events',
            {
                'form_type': 'event',
                'full_name': 'Jamie Taylor',
                'mobile_number': '+1 (555) 123-4567',
                'email': '',
                'area_city': 'Chennai',
                'preferred_contact_method': 'phone',
                'event': str(event.pk),
                'preferred_at': '',
                'message': '',
                'consent': 'on',
            },
        )

        self.assertRedirects(response, f'/#event-{event.pk}')
        self.assertEqual(EventRegistration.objects.count(), 1)
        self.assertEqual(
            EventRegistration.objects.get().event,
            event,
        )

    def test_registration_without_an_event_is_rejected(self):
        starts_at = timezone.now() + timedelta(days=7)
        for title in ('Community walk', 'Wellness gathering'):
            CommunityEvent.objects.create(
                title=title,
                description='An upcoming activity.',
                starts_at=starts_at,
                is_published=True,
            )

        response = self.client.post(
            '/',
            {
                'form_type': 'event',
                'full_name': 'Jamie Taylor',
                'mobile_number': '5551234567',
                'email': '',
                'preferred_at': '',
                'message': '',
                'consent': 'on',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'registration for this event is not open')
        self.assertEqual(EventRegistration.objects.count(), 0)

    def test_event_registration_requires_consent_and_valid_phone(self):
        event = CommunityEvent.objects.create(
            title='Community walk',
            description='A relaxed walk together.',
            starts_at=timezone.now() + timedelta(days=7),
            is_published=True,
        )

        response = self.client.post(
            '/',
            {
                'form_type': 'event',
                'full_name': 'Jamie Taylor',
                'mobile_number': '-------1',
                'email': 'not-an-email',
                'event': str(event.pk),
                'message': '',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'at least 7 digits')
        self.assertContains(response, 'This field is required.')
        self.assertEqual(EventRegistration.objects.count(), 0)
        # The card that was submitted re-opens with its errors.
        self.assertContains(response, f'id="event-dialog-{event.pk}" aria-labelledby="event-dialog-title-{event.pk}" data-open-on-load')

    def test_valid_community_interest_is_saved(self):
        response = self.client.post(
            '/',
            {
                'form_type': 'community',
                'full_name': 'Jamie Taylor',
                'mobile_number': '5551234567',
                'email': '',
                'area_city': 'Riverdale',
                'area_of_interest': 'community-activities',
                'preferred_contact_method': 'whatsapp',
                'message': 'I would like to join local activities.',
                'consent': 'on',
            },
        )

        self.assertRedirects(response, '/#join')
        self.assertEqual(CommunityInterest.objects.count(), 1)
        interest = CommunityInterest.objects.get()
        self.assertTrue(interest.consent)
        self.assertEqual(interest.mobile_number, '5551234567')

    def test_email_contact_requires_an_email_address(self):
        response = self.client.post(
            '/',
            {
                'form_type': 'community',
                'full_name': 'Jamie Taylor',
                'mobile_number': '5551234567',
                'email': '',
                'area_city': '',
                'area_of_interest': 'general-information',
                'preferred_contact_method': 'email',
                'message': '',
                'consent': 'on',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Add an email address to be contacted by email.')
        self.assertEqual(CommunityInterest.objects.count(), 0)
        # The optional-details panel holding the email field opens to show the error.
        content = response.content.decode()
        join_form = content[content.index('id="join"'):]
        self.assertIn('<details class="consult-more" open>', join_form)


def consultation_data(**overrides):
    data = {
        'form_type': 'consultation',
        'full_name': 'Priya Kumar',
        'mobile_number': '+91 98765 43210',
        'email': 'priya@example.com',
        'area_city': 'Chennai',
        'service': '',
        'goal': 'weight-loss',
        'consultation_mode': 'online',
        'preferred_at': '',
        'preferred_contact_method': 'whatsapp',
        'message': '',
        'consent': 'on',
    }
    data.update(overrides)
    return data


class WellnessCoachingTests(TestCase):
    def test_starter_services_are_listed_with_booking_links(self):
        response = self.client.get('/')

        self.assertContains(response, 'Weight management')
        self.assertContains(response, '?service=weight-management#consultation')

    def test_unpublished_service_is_hidden(self):
        Service.objects.filter(slug='weight-management').update(is_published=False)

        response = self.client.get('/')

        self.assertNotContains(response, '?service=weight-management')

    def test_service_link_preselects_the_service_in_the_form(self):
        service = Service.objects.get(slug='nutrition-coaching')

        response = self.client.get('/?service=nutrition-coaching')

        self.assertEqual(response.context['consultation_form'].initial['service'], service)

    def test_valid_consultation_is_saved_as_new(self):
        service = Service.objects.get(slug='weight-management')

        response = self.client.post('/', consultation_data(service=str(service.pk)))

        self.assertRedirects(response, '/#consultation')
        consultation = WellnessConsultation.objects.get()
        self.assertEqual(consultation.service, service)
        self.assertEqual(consultation.status, 'new')
        self.assertTrue(consultation.consent)

    def test_consultation_requires_consent_and_goal(self):
        data = consultation_data(goal='')
        del data['consent']

        response = self.client.post('/', data)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'This field is required.')
        self.assertEqual(WellnessConsultation.objects.count(), 0)

    @override_settings(COACH_NOTIFICATION_EMAILS=['coach@example.com'], BREVO_API_KEY='')
    def test_coach_is_emailed_about_new_submissions(self):
        self.client.post('/', consultation_data())
        self.client.post('/', {
            'form_type': 'community',
            'full_name': 'Jamie Taylor',
            'mobile_number': '5551234567',
            'area_of_interest': 'wellness-sessions',
            'preferred_contact_method': 'phone',
            'consent': 'on',
        })

        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(mail.outbox[0].to, ['coach@example.com'])
        self.assertIn('consultation', mail.outbox[0].subject)
        self.assertIn('Priya Kumar', mail.outbox[0].body)
        self.assertIn('Weight loss', mail.outbox[0].body)
        self.assertEqual(len(mail.outbox[0].alternatives), 1)
        self.assertIn('<table', mail.outbox[0].alternatives[0][0])
        self.assertIn('New website submission', mail.outbox[0].alternatives[0][0])

    @override_settings(COACH_NOTIFICATION_EMAILS=[], BREVO_API_KEY='')
    def test_no_email_is_sent_without_configured_recipients(self):
        self.client.post('/', consultation_data())

        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(WellnessConsultation.objects.count(), 1)

    @override_settings(
        BREVO_API_KEY='test-api-key',
        BREVO_SENDER_EMAIL='verified@example.com',
        COACH_NOTIFICATION_EMAILS=['doddinikki185@gmail.com'],
    )
    @patch('baggi.notifications.urlopen')
    def test_brevo_receives_submission_at_configured_destination(self, mock_urlopen):
        self.client.post('/', consultation_data())

        request = mock_urlopen.call_args.args[0]
        payload = json.loads(request.data)
        self.assertEqual(request.full_url, 'https://api.brevo.com/v3/smtp/email')
        self.assertEqual(request.get_header('Api-key'), 'test-api-key')
        self.assertEqual(payload['to'], [{'email': 'doddinikki185@gmail.com'}])
        self.assertIn('Priya Kumar', payload['textContent'])
        self.assertIn('Weight loss', payload['textContent'])
        self.assertIn('Consent: Yes', payload['textContent'])
        self.assertIn('<table', payload['htmlContent'])
        self.assertIn('New website submission', payload['htmlContent'])

    def test_only_consented_published_success_story_is_shown(self):
        SuccessStory.objects.create(client_name='R.', quote='Hidden draft story', client_consent=True)
        SuccessStory.objects.create(client_name='S.', quote='No consent story', is_published=True)
        response = self.client.get('/')
        self.assertNotContains(response, 'Hidden draft story')
        self.assertNotContains(response, 'No consent story')

        SuccessStory.objects.create(
            client_name='Meena', quote='I feel more energetic every day.',
            client_consent=True, is_published=True,
        )
        response = self.client.get('/')
        self.assertContains(response, 'I feel more energetic every day.')

    def test_admin_can_export_consultations_to_csv(self):
        self.client.post('/', consultation_data())
        consultation = WellnessConsultation.objects.get()
        admin_user = get_user_model().objects.create_superuser('coach', 'coach@example.com', 'pass')
        self.client.force_login(admin_user)

        response = self.client.post(
            '/admin/baggi/wellnessconsultation/',
            {'action': 'export_as_csv', '_selected_action': [consultation.pk]},
        )

        self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')
        content = response.content.decode('utf-8-sig')
        self.assertIn('Priya Kumar', content)
        self.assertIn('Weight loss', content)

    def test_admin_can_export_read_only_community_enquiries(self):
        interest = CommunityInterest.objects.create(
            full_name='Jamie Taylor', mobile_number='5551234567',
            area_of_interest='wellness-sessions', preferred_contact_method='phone', consent=True,
        )
        admin_user = get_user_model().objects.create_superuser('coach', 'coach@example.com', 'pass')
        self.client.force_login(admin_user)

        response = self.client.post(
            '/admin/baggi/communityinterest/',
            {'action': 'export_as_csv', '_selected_action': [interest.pk]},
        )

        self.assertIn('Jamie Taylor', response.content.decode('utf-8-sig'))


def make_event(**overrides):
    data = {
        'title': 'Healthy breakfast workshop',
        'description': 'Learn simple balanced breakfasts.',
        'starts_at': timezone.now() + timedelta(days=5),
        'venue': 'Anna Nagar Community Hall',
        'is_published': True,
    }
    data.update(overrides)
    return CommunityEvent.objects.create(**data)


def registration_data(event, **overrides):
    data = {
        'form_type': 'event',
        'full_name': 'Priya Kumar',
        'mobile_number': '+91 98765 43210',
        'email': 'priya@example.com',
        'area_city': 'Chennai',
        'preferred_contact_method': 'whatsapp',
        'event': str(event.pk),
        'attendees': '1',
        'message': '',
        'consent': 'on',
    }
    data.update(overrides)
    return data


class EventRegistrationControlTests(TestCase):
    def test_event_card_shows_date_time_venue_and_seats(self):
        starts_at = timezone.now() + timedelta(days=5)
        event = make_event(starts_at=starts_at, ends_at=starts_at + timedelta(hours=2), capacity=20)

        response = self.client.get('/')

        self.assertContains(response, 'Healthy breakfast workshop')
        self.assertContains(response, 'Anna Nagar Community Hall')
        self.assertContains(response, '20 places left')
        self.assertContains(response, f'id="event-{event.pk}"')
        self.assertContains(response, 'Register for this event')
        self.assertContains(response, f'id="id_event{event.pk}_full_name"')

    def test_each_open_event_card_has_its_own_form_for_that_event(self):
        first = make_event(title='First')
        second = make_event(title='Second')

        response = self.client.get('/')

        forms = {event.pk: event.registration_form for event in response.context['events']}
        self.assertEqual(forms[first.pk].initial['event'], first.pk)
        self.assertEqual(forms[second.pk].initial['event'], second.pk)
        self.assertContains(response, f'name="event" value="{first.pk}"')
        self.assertContains(response, f'name="event" value="{second.pk}"')

        self.client.post('/', registration_data(second))
        self.assertEqual(EventRegistration.objects.get().event, second)

    def test_event_link_opens_that_events_form(self):
        make_event(title='First')
        second = make_event(title='Second')

        response = self.client.get(f'/?event={second.pk}')

        expanded = [event.pk for event in response.context['events'] if event.form_expanded]
        self.assertEqual(expanded, [second.pk])

    def test_closed_event_is_listed_without_a_registration_form(self):
        event = make_event(registration_open=False)

        response = self.client.get('/')

        self.assertContains(response, 'Registration closed')
        self.assertNotContains(response, 'class="event-dialog"')
        self.assertNotContains(response, f'name="event" value="{event.pk}"')

        self.client.post('/', registration_data(event))
        self.assertEqual(EventRegistration.objects.count(), 0)

    def test_registration_closes_at_the_deadline(self):
        make_event(registration_closes_at=timezone.now() - timedelta(minutes=1))

        self.assertContains(self.client.get('/'), 'Registration closed')

    def test_full_event_rejects_more_registrations(self):
        event = make_event(capacity=3)
        self.client.post('/', registration_data(event, attendees='2'))
        self.assertEqual(EventRegistration.objects.count(), 1)

        response = self.client.post('/', registration_data(event, mobile_number='9000000001', attendees='2'))
        self.assertContains(response, 'Only 1 place(s) left for this event.')

        self.client.post('/', registration_data(event, mobile_number='9000000001', attendees='1'))
        self.assertEqual(EventRegistration.objects.count(), 2)
        self.assertContains(self.client.get('/'), 'Fully booked')

    def test_same_mobile_cannot_register_twice_for_one_event(self):
        event = make_event()
        self.client.post('/', registration_data(event))

        response = self.client.post('/', registration_data(event, mobile_number='+91-98765-43210'))

        self.assertContains(response, 'already registered for this event')
        self.assertEqual(EventRegistration.objects.count(), 1)

    def test_event_end_time_must_be_after_start(self):
        starts_at = timezone.now() + timedelta(days=5)
        event = CommunityEvent(
            title='Bad', description='x', starts_at=starts_at, ends_at=starts_at - timedelta(hours=1),
        )

        with self.assertRaisesMessage(Exception, 'end time must be after the start time'):
            event.full_clean()

    def test_admin_can_add_event_and_see_registrations(self):
        admin_user = get_user_model().objects.create_superuser('coach', 'coach@example.com', 'pass')
        self.client.force_login(admin_user)
        start = timezone.localtime(timezone.now() + timedelta(days=3))

        response = self.client.post('/admin/baggi/communityevent/add/', {
            'title': 'Weekend wellness walk',
            'description': 'A 5 km walk.',
            'starts_at_0': start.strftime('%Y-%m-%d'),
            'starts_at_1': '07:00:00',
            'ends_at_0': start.strftime('%Y-%m-%d'),
            'ends_at_1': '08:30:00',
            'venue': 'Marina Beach',
            'registration_open': 'on',
            'capacity': '30',
            'is_published': 'on',
            
            
        })

        self.assertEqual(response.status_code, 302, getattr(response, 'context', None) and response.context['adminform'].form.errors)
        event = CommunityEvent.objects.get(title='Weekend wellness walk')
        self.client.post('/', registration_data(event))
        self.client.force_login(admin_user)

        changelist = self.client.get('/admin/baggi/communityevent/')
        self.assertContains(changelist, '1 / 30')
        change_page = self.client.get(f'/admin/baggi/communityevent/{event.pk}/change/')
        self.assertContains(change_page, 'Priya Kumar')

    def test_visitors_cannot_add_events(self):
        response = self.client.get('/admin/baggi/communityevent/add/')

        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/login/', response.url)


class AdminFullAccessTests(TestCase):
    def setUp(self):
        self.admin_user = get_user_model().objects.create_superuser('coach', 'coach@example.com', 'pass')
        self.client.force_login(self.admin_user)
        self.event = make_event()
        self.objects = {
            'communityevent': self.event,
            'eventregistration': EventRegistration.objects.create(
                full_name='Priya Kumar', mobile_number='9876543210', event=self.event, consent=True,
            ),
            'communityinterest': CommunityInterest.objects.create(
                full_name='Jamie Taylor', mobile_number='5551234567',
                area_of_interest='wellness-sessions', preferred_contact_method='phone', consent=True,
            ),
            'wellnessconsultation': WellnessConsultation.objects.create(
                full_name='Meena', mobile_number='9000000000', goal='weight-loss',
                preferred_contact_method='phone', consent=True,
            ),
            'service': Service.objects.first(),
            'successstory': SuccessStory.objects.create(client_name='R.', quote='Great support.'),
            'review': Review.objects.create(full_name='Anu', rating=5, review='Great coaching support.'),
        }

    def test_every_module_has_add_edit_and_delete(self):
        for model_name, obj in self.objects.items():
            with self.subTest(model=model_name):
                base = f'/admin/baggi/{model_name}/'
                changelist = self.client.get(base)
                self.assertContains(changelist, f'{base}add/')
                self.assertContains(changelist, 'delete_selected')
                self.assertContains(changelist, f'<a class="row-action row-edit" href="{base}{obj.pk}/change/"')
                self.assertContains(changelist, f'<a class="row-action row-delete" href="{base}{obj.pk}/delete/"')
                # The actions sit in the first column, before the record's own fields.
                content = changelist.content.decode()
                first_row = content[content.index('<tbody>'):]
                first_field = first_row.index('class="field-')
                self.assertEqual(first_row.index('class="field-row_actions"'), first_field)
                self.assertEqual(self.client.get(f'{base}add/').status_code, 200)
                change_page = self.client.get(f'{base}{obj.pk}/change/')
                self.assertContains(change_page, 'name="_save"')
                self.assertContains(change_page, f'{base}{obj.pk}/delete/')

    def test_admin_can_edit_a_registration(self):
        registration = self.objects['eventregistration']

        response = self.client.post(f'/admin/baggi/eventregistration/{registration.pk}/change/', {
            'full_name': 'Priya K.',
            'mobile_number': '9876543210',
            'email': '',
            'event': str(self.event.pk),
            'attendees': '3',
            'message': '',
            'consent': 'on',
        })

        self.assertEqual(response.status_code, 302)
        registration.refresh_from_db()
        self.assertEqual((registration.full_name, registration.attendees), ('Priya K.', 3))

    def test_admin_can_add_and_delete_a_registration(self):
        response = self.client.post('/admin/baggi/eventregistration/add/', {
            'full_name': 'Walk-in guest',
            'mobile_number': '9111111111',
            'email': '',
            'event': str(self.event.pk),
            'attendees': '1',
            'message': '',
        })
        self.assertEqual(response.status_code, 302)
        added = EventRegistration.objects.get(full_name='Walk-in guest')

        self.client.post(f'/admin/baggi/eventregistration/{added.pk}/delete/', {'post': 'yes'})

        self.assertFalse(EventRegistration.objects.filter(pk=added.pk).exists())

    def test_admin_can_delete_an_enquiry(self):
        interest = self.objects['communityinterest']

        self.client.post('/admin/baggi/communityinterest/', {
            'action': 'delete_selected', '_selected_action': [interest.pk], 'post': 'yes',
        })

        self.assertFalse(CommunityInterest.objects.filter(pk=interest.pk).exists())


def png_upload(name='walk.png'):
    from django.core.files.uploadedfile import SimpleUploadedFile
    from PIL import Image

    buffer = io.BytesIO()
    Image.new('RGB', (32, 18), (11, 27, 48)).save(buffer, format='PNG')
    return SimpleUploadedFile(name, buffer.getvalue(), content_type='image/png')


class EventImageTests(TestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media_root, ignore_errors=True)
        override = override_settings(MEDIA_ROOT=self.media_root)
        override.enable()
        self.addCleanup(override.disable)
        admin_user = get_user_model().objects.create_superuser('coach', 'coach@example.com', 'pass')
        self.client.force_login(admin_user)

    def event_form_data(self, image):
        start = timezone.localtime(timezone.now() + timedelta(days=3))
        return {
            'title': 'Sunrise yoga',
            'description': 'Gentle morning yoga.',
            'image': image,
            'starts_at_0': start.strftime('%Y-%m-%d'),
            'starts_at_1': '06:30:00',
            'venue': 'Marina Beach',
            'registration_open': 'on',
            'is_published': 'on',
        }

    def test_admin_uploads_event_image_and_it_shows_on_the_card(self):
        response = self.client.post('/admin/baggi/communityevent/add/', self.event_form_data(png_upload()))

        self.assertEqual(response.status_code, 302)
        event = CommunityEvent.objects.get(title='Sunrise yoga')
        self.assertTrue(event.image.name.startswith('events/'))
        self.assertContains(self.client.get('/'), f'<img class="event-image" src="{event.image.url}"')
        self.assertContains(self.client.get('/admin/baggi/communityevent/'), event.image.url)

    def test_non_image_file_is_rejected(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        fake = SimpleUploadedFile('notes.png', b'not really an image', content_type='image/png')
        response = self.client.post('/admin/baggi/communityevent/add/', self.event_form_data(fake))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(CommunityEvent.objects.filter(title='Sunrise yoga').exists())

    def test_event_without_image_still_shows(self):
        make_event(title='No photo event')

        response = self.client.get('/')

        self.assertContains(response, 'No photo event')
        self.assertNotContains(response, 'class="event-image"')


def review_data(**overrides):
    data = {
        'form_type': 'review',
        'full_name': 'Meena',
        'service': '',
        'rating': '5',
        'review': 'The coaching helped me build healthy habits and feel more energetic.',
        'area_city': 'Chennai',
        'consent_to_publish': 'on',
        'website': '',
    }
    data.update(overrides)
    return data


class ReviewTests(TestCase):
    def test_submitted_review_waits_for_approval(self):
        service = Service.objects.get(slug='weight-management')

        response = self.client.post('/', review_data(service=str(service.pk)))

        self.assertRedirects(response, '/#reviews')
        review = Review.objects.get()
        self.assertFalse(review.is_approved)
        self.assertEqual((review.rating, review.service), (5, service))
        self.assertNotContains(self.client.get('/'), 'feel more energetic')

    def test_approved_reviews_show_with_average_rating(self):
        service = Service.objects.get(slug='nutrition-coaching')
        Review.objects.create(full_name='Meena', rating=5, review='Wonderful support every week.',
                              service=service, is_approved=True, consent_to_publish=True)
        Review.objects.create(full_name='Ravi', rating=4, review='Practical and friendly advice.',
                              is_approved=True, consent_to_publish=True)
        Review.objects.create(full_name='Hidden', rating=1, review='Not approved yet.')

        response = self.client.get('/')

        self.assertContains(response, 'Wonderful support every week.')
        self.assertContains(response, 'Nutrition coaching')
        self.assertContains(response, 'Based on 2 reviews')
        self.assertContains(response, '<strong>4.5</strong>', html=True)
        self.assertNotContains(response, 'Not approved yet.')
        self.assertContains(response, 'Individual results vary')

    def test_empty_state_invites_first_review(self):
        response = self.client.get('/')

        self.assertContains(response, 'Be the first to share your experience')
        self.assertContains(response, 'data-dialog="review-dialog"')

    def test_rating_and_consent_are_required_and_popup_reopens(self):
        data = review_data(rating='')
        del data['consent_to_publish']

        response = self.client.post('/', data)

        self.assertContains(response, 'Please choose a star rating.')
        self.assertContains(response, 'id="review-dialog" aria-labelledby="review-dialog-title" data-open-on-load')
        self.assertEqual(Review.objects.count(), 0)

    def test_out_of_range_rating_is_rejected(self):
        self.client.post('/', review_data(rating='9'))

        self.assertEqual(Review.objects.count(), 0)

    def test_spam_bot_filling_hidden_field_is_rejected(self):
        self.client.post('/', review_data(website='http://spam.example'))

        self.assertEqual(Review.objects.count(), 0)

    @override_settings(COACH_NOTIFICATION_EMAILS=['coach@example.com'], BREVO_API_KEY='')
    def test_coach_is_emailed_about_new_review(self):
        self.client.post('/', review_data())

        self.assertIn('review', mail.outbox[0].subject)

    def test_admin_approve_action_publishes_reviews(self):
        review = Review.objects.create(full_name='Meena', rating=5, review='Lovely coaching sessions.',
                                       consent_to_publish=True)
        admin_user = get_user_model().objects.create_superuser('coach', 'coach@example.com', 'pass')
        self.client.force_login(admin_user)

        self.client.post('/admin/baggi/review/', {'action': 'approve_reviews', '_selected_action': [review.pk]})

        review.refresh_from_db()
        self.assertTrue(review.is_approved)
        self.assertContains(self.client.get('/'), 'Lovely coaching sessions.')


class ReviewShowMoreAndPhotoTests(TestCase):
    def make_reviews(self, count):
        return [
            Review.objects.create(full_name=f'Client {n}', rating=5, review=f'Review number {n} text.',
                                  is_approved=True, consent_to_publish=True)
            for n in range(1, count + 1)
        ]

    def test_only_four_reviews_visible_until_show_more(self):
        self.make_reviews(6)

        response = self.client.get('/')
        content = response.content.decode()

        self.assertEqual(content.count('class="review-card'), 6)
        self.assertEqual(content.count(' review-extra"'), 2)
        self.assertEqual(content.count('data-reveal style="--delay: 0ms" hidden'), 1)
        self.assertContains(response, 'Show more reviews (2)')
        self.assertContains(response, 'Based on 6 reviews')

    def test_no_show_more_button_with_four_or_fewer(self):
        self.make_reviews(4)

        response = self.client.get('/')

        self.assertNotContains(response, 'id="reviews-more"')
        self.assertNotContains(response, ' review-extra')

    def test_before_and_after_photos_show_on_card_and_popup(self):
        media_root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, media_root, ignore_errors=True)
        with override_settings(MEDIA_ROOT=media_root):
            review = Review.objects.create(
                full_name='Meena', rating=5, review='Lost weight the healthy way.', is_approved=True,
                consent_to_publish=True, before_photo=png_upload('before.png'), after_photo=png_upload('after.png'),
            )

            response = self.client.get('/')

        self.assertContains(response, f'data-dialog="review-photos-{review.pk}"')
        self.assertContains(response, review.before_photo.url, count=2)
        self.assertContains(response, review.after_photo.url, count=2)
        self.assertContains(response, '<em class="is-after">After</em>', html=True)
        self.assertContains(response, 'Meena’s journey')

    def test_admin_can_upload_before_and_after_photos(self):
        media_root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, media_root, ignore_errors=True)
        review = Review.objects.create(full_name='Meena', rating=5, review='Great coaching.', consent_to_publish=True)
        admin_user = get_user_model().objects.create_superuser('coach', 'coach@example.com', 'pass')
        self.client.force_login(admin_user)

        with override_settings(MEDIA_ROOT=media_root):
            response = self.client.post(f'/admin/baggi/review/{review.pk}/change/', {
                'full_name': 'Meena', 'area_city': '', 'service': '', 'rating': '5',
                'review': 'Great coaching.', 'consent_to_publish': 'on', 'is_approved': 'on',
                'before_photo': png_upload('before.png'), 'after_photo': png_upload('after.png'),
            })
            self.assertEqual(response.status_code, 302)
            review.refresh_from_db()
            self.assertTrue(review.before_photo.name.startswith('reviews/'))
            self.assertTrue(review.after_photo.name.startswith('reviews/'))
            change_page = self.client.get(f'/admin/baggi/review/{review.pk}/change/')
            self.assertContains(change_page, 'Before &amp; after transformation')
            self.assertContains(change_page, review.after_photo.url)


class ServicePriceTests(TestCase):
    def test_price_shows_in_indian_format_with_unit_and_offer(self):
        Service.objects.filter(slug='weight-management').update(
            price=Decimal('125000'), original_price=Decimal('150000'), price_unit='per 3 months',
        )

        response = self.client.get('/')

        self.assertContains(response, '<span class="svc-currency">₹</span>1,25,000')
        self.assertContains(response, '₹1,50,000</s>')
        self.assertContains(response, '<small>per 3 months</small>', html=True)

    def test_zero_price_shows_free_and_blank_price_is_hidden(self):
        Service.objects.filter(slug='wellness-evaluation').update(price=Decimal('0'))

        response = self.client.get('/')
        content = response.content.decode()

        self.assertContains(response, '<strong>Free</strong>', html=True)
        self.assertEqual(content.count('class="svc-price"'), 1)

    def test_original_price_must_be_higher(self):
        service = Service(title='Test', slug='test', summary='x', price=Decimal('500'), original_price=Decimal('400'))

        with self.assertRaisesMessage(Exception, 'original price should be higher'):
            service.full_clean()

    def test_admin_adds_new_service_that_appears_in_same_design(self):
        admin_user = get_user_model().objects.create_superuser('coach', 'coach@example.com', 'pass')
        self.client.force_login(admin_user)

        response = self.client.post('/admin/baggi/service/add/', {
            'title': 'Sports nutrition',
            'slug': 'sports-nutrition',
            'icon': '☀',
            'summary': 'Fuel your training with the right balance of nutrients.',
            'price': '2499',
            'original_price': '',
            'price_unit': 'per month',
            'display_order': '5',
            'is_published': 'on',
        })

        self.assertEqual(response.status_code, 302)
        home = self.client.get('/')
        self.assertContains(home, '<h3>Sports nutrition</h3>', html=True)
        self.assertContains(home, '<span class="svc-currency">₹</span>2,499')
        self.assertContains(home, '?service=sports-nutrition#consultation')
        self.assertContains(home, '<span class="svc-num">05</span>', html=True)

    def test_admin_can_edit_prices_from_the_list(self):
        admin_user = get_user_model().objects.create_superuser('coach', 'coach@example.com', 'pass')
        self.client.force_login(admin_user)

        changelist = self.client.get('/admin/baggi/service/')

        self.assertContains(changelist, 'name="form-0-price"')
        self.assertContains(changelist, 'name="form-0-price_unit"')


class ServiceSliderTests(TestCase):
    def test_service_cards_sit_in_a_slider_with_controls(self):
        for n in range(5, 9):
            Service.objects.create(title=f'Extra service {n}', slug=f'extra-{n}', summary='More support.', display_order=n)

        response = self.client.get('/')
        content = response.content.decode()

        self.assertContains(response, 'data-slider-track')
        self.assertContains(response, 'data-slider-prev')
        self.assertContains(response, 'data-slider-next')
        track = content[content.index('data-slider-track'):content.index('data-slider-next')]
        self.assertEqual(track.count('class="svc-card"'), 8)


class RecentEventsPaginationTests(TestCase):
    def setUp(self):
        now = timezone.now()
        for n in range(1, 8):  # Past event 1 is the most recent.
            make_event(title=f'Past event {n}', starts_at=now - timedelta(days=n))

    def past_names(self, response):
        return [event.title for event in response.context['past_events']]

    def test_first_page_shows_three_most_recent(self):
        response = self.client.get('/')

        self.assertEqual(self.past_names(response), ['Past event 1', 'Past event 2', 'Past event 3'])
        self.assertContains(response, '1–3 of 7')
        self.assertContains(response, 'href="?past_page=2#recent-events"')
        self.assertContains(response, '<span class="pager-num is-current" aria-current="page">1</span>', html=True)

    def test_later_pages_and_last_page(self):
        self.assertEqual(self.past_names(self.client.get('/?past_page=2')), ['Past event 4', 'Past event 5', 'Past event 6'])
        last = self.client.get('/?past_page=3')
        self.assertEqual(self.past_names(last), ['Past event 7'])
        self.assertContains(last, 'href="?past_page=2#recent-events" aria-label="Previous page"')

    def test_invalid_page_numbers_fall_back_safely(self):
        self.assertEqual(self.past_names(self.client.get('/?past_page=99')), ['Past event 7'])
        self.assertEqual(self.past_names(self.client.get('/?past_page=abc'))[0], 'Past event 1')

    def test_no_pager_with_three_or_fewer(self):
        CommunityEvent.objects.filter(title__in=['Past event 4', 'Past event 5', 'Past event 6', 'Past event 7']).delete()

        response = self.client.get('/')

        self.assertNotContains(response, 'class="pager"')
        self.assertEqual(len(self.past_names(response)), 3)


class SiteSettingsTests(TestCase):
    def test_admin_whatsapp_number_powers_floating_button_on_every_page(self):
        site = SiteSettings.load()
        site.whatsapp_number = '+91 98765 43210'
        site.whatsapp_message = 'Hello coach!'
        site.save()

        for url in ('/', '/privacy/'):
            with self.subTest(url=url):
                self.assertContains(self.client.get(url), 'href="https://wa.me/919876543210?text=Hello%20coach%21"')

    @override_settings(COMMUNITY_WHATSAPP_NUMBER='+1 555 000 1111')
    def test_admin_number_wins_over_settings_file(self):
        site = SiteSettings.load()
        site.whatsapp_number = '+91 90000 00000'
        site.save()

        response = self.client.get('/')

        self.assertContains(response, 'https://wa.me/919000000000')
        self.assertNotContains(response, 'https://wa.me/15550001111')

    def test_only_filled_social_links_show_in_footer(self):
        site = SiteSettings.load()
        site.instagram_url = 'https://instagram.com/coach'
        site.youtube_url = 'https://youtube.com/@coach'
        site.save()

        response = self.client.get('/')

        self.assertContains(response, 'Follow us')
        self.assertContains(response, 'href="https://instagram.com/coach"')
        self.assertContains(response, 'href="https://youtube.com/@coach"')
        self.assertNotContains(response, 'class="social-facebook"')

    def test_no_follow_block_without_any_links(self):
        self.assertNotContains(self.client.get('/'), 'Follow us')

    def test_footer_shows_phone_and_email(self):
        site = SiteSettings.load()
        site.phone = '+91 98765 43210'
        site.email = 'coach@example.com'
        site.save()

        response = self.client.get('/')

        self.assertContains(response, 'href="tel:+919876543210"')
        self.assertContains(response, 'href="mailto:coach@example.com"')

    def test_settings_admin_is_a_single_page(self):
        admin_user = get_user_model().objects.create_superuser('coach', 'coach@example.com', 'pass')
        self.client.force_login(admin_user)

        response = self.client.get('/admin/baggi/sitesettings/')

        self.assertRedirects(response, '/admin/baggi/sitesettings/1/change/')
        self.assertEqual(self.client.get('/admin/baggi/sitesettings/add/').status_code, 403)
        page = self.client.get('/admin/baggi/sitesettings/1/change/')
        self.assertContains(page, 'WhatsApp chat button')
        self.assertContains(page, 'Social media (footer icons)')


class AboutSlideshowTests(TestCase):
    def test_built_in_exercise_photos_show_by_default(self):
        response = self.client.get('/')

        self.assertContains(response, 'class="about-slide', count=6)
        self.assertContains(response, 'baggi/media/about/exercise-1.jpg')
        self.assertContains(response, 'aria-label="Show photo ', count=6)

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_uploaded_photos_replace_the_defaults(self):
        for order, name in enumerate(['first', 'second']):
            AboutPhoto.objects.create(
                image=png_upload(f'{name}.png'),
                alt_text=f'{name} photo',
                sort_order=order,
            )
        AboutPhoto.objects.create(
            image=png_upload('hidden.png'),
            alt_text='hidden photo',
            is_published=False,
        )

        response = self.client.get('/')

        self.assertContains(response, 'class="about-slide', count=2)
        self.assertContains(response, 'alt="first photo"')
        self.assertNotContains(response, 'hidden photo')
        self.assertNotContains(response, 'exercise-1.jpg')

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_single_photo_has_no_dots(self):
        AboutPhoto.objects.create(
            image=png_upload('only.png'),
            alt_text='only photo',
        )

        response = self.client.get('/')

        self.assertContains(response, 'class="about-slide', count=1)
        self.assertNotContains(response, 'class="about-dots"')


class AdminLayoutTests(TestCase):
    def setUp(self):
        self.admin_user = get_user_model().objects.create_superuser('coach', 'coach@example.com', 'pass')
        self.client.force_login(self.admin_user)

    def test_dashboard_shows_counts_bookings_and_events(self):
        WellnessConsultation.objects.create(
            full_name='Priya N', mobile_number='+91 90000 00001', goal='weight-loss',
            preferred_contact_method='phone', consent=True,
        )
        Review.objects.create(full_name='Sam', rating=5, review='Great', consent_to_publish=True)
        CommunityEvent.objects.create(
            title='Morning walk', description='Walk', starts_at=timezone.now() + timedelta(days=3),
            is_published=True, is_online=True,
        )

        response = self.client.get('/admin/')

        self.assertContains(response, 'class="cw-sidebar"')
        self.assertContains(response, 'New consultation bookings')
        self.assertContains(response, 'href="/admin/baggi/wellnessconsultation/?status__exact=new"')
        self.assertContains(response, 'href="/admin/baggi/review/?is_approved__exact=0"')
        self.assertContains(response, 'Priya N')
        self.assertContains(response, 'Morning walk')
        # Sidebar badges for items waiting on the coach.
        self.assertContains(response, 'class="cw-badge" title="1 waiting"', count=2)

    def test_sidebar_groups_and_marks_current_page(self):
        response = self.client.get('/admin/baggi/service/')

        self.assertContains(response, '<p class="cw-nav-title">Enquiries</p>', html=True)
        self.assertContains(response, '<p class="cw-nav-title">Website</p>', html=True)
        self.assertContains(response, '<p class="cw-nav-title">Settings</p>', html=True)
        self.assertContains(response, 'class="cw-nav-link is-active" href="/admin/baggi/service/"')
        self.assertNotContains(response, 'id="nav-sidebar"')

    def test_booking_badge_clears_after_visiting_the_list(self):
        def booking(name):
            return WellnessConsultation.objects.create(
                full_name=name, mobile_number='+91 90000 00009', goal='weight-loss',
                preferred_contact_method='phone', consent=True,
            )

        booking('First')
        badge = '<b class="cw-badge" title="1 waiting">1</b>'
        self.assertContains(self.client.get('/admin/'), badge)

        list_page = self.client.get('/admin/baggi/wellnessconsultation/')
        self.assertNotContains(list_page, badge)
        self.assertNotContains(self.client.get('/admin/'), badge)

        booking('Second')
        self.assertContains(self.client.get('/admin/'), badge)

    def test_list_pages_load_the_filter_dropdown_script(self):
        response = self.client.get('/admin/baggi/communityevent/')

        self.assertContains(response, 'id="changelist-filter"')
        self.assertContains(response, 'baggi/admin.js')

    def test_staff_without_permissions_sees_no_stats(self):
        staff = get_user_model().objects.create_user('helper', 'h@example.com', 'pass', is_staff=True)
        self.client.force_login(staff)

        response = self.client.get('/admin/')

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'cw-stat ')
        self.assertNotContains(response, 'Latest bookings')

    def test_login_page_keeps_brand_without_sidebar(self):
        self.client.logout()

        response = self.client.get('/admin/login/')

        self.assertContains(response, 'admin-brand')
        self.assertNotContains(response, 'cw-sidebar')


class ServiceBookingPopupTests(TestCase):
    def setUp(self):
        self.service = Service.objects.filter(is_published=True).first()

    def booking_data(self, **overrides):
        data = {
            'form_type': 'book',
            'book-service': self.service.pk,
            'book-full_name': 'Asha R',
            'book-mobile_number': '+91 90000 00002',
            'book-email': 'asha@example.com',
            'book-goal': 'weight-loss',
            'book-consultation_mode': 'online',
            'book-preferred_contact_method': 'phone',
            'book-consent': 'on',
        }
        data.update(overrides)
        return data

    def test_book_this_opens_the_popup_for_that_service(self):
        response = self.client.get('/')

        self.assertContains(response, 'id="book-dialog"')
        self.assertContains(response, f'data-dialog="book-dialog" data-book-service="{self.service.pk}"')
        self.assertNotContains(response, 'id="book-dialog" aria-labelledby="book-dialog-title" data-open-on-load')

    def test_valid_booking_saves_with_the_service(self):
        response = self.client.post('/', self.booking_data())

        self.assertRedirects(response, '/#services', fetch_redirect_response=False)
        booking = WellnessConsultation.objects.get()
        self.assertEqual(booking.service, self.service)
        self.assertEqual(booking.full_name, 'Asha R')
        self.assertEqual(booking.source, 'service')

    def test_invalid_booking_reopens_popup_with_service_title(self):
        response = self.client.post('/', self.booking_data(**{'book-consent': ''}))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(WellnessConsultation.objects.count(), 0)
        self.assertContains(response, 'data-open-on-load')
        self.assertContains(response, f'data-book-heading>{self.service.title}</h3>')


class ConsultationEmailRuleTests(TestCase):
    def test_email_is_optional_for_other_contact_methods(self):
        self.client.post('/', consultation_data(email='', preferred_contact_method='whatsapp'))

        self.assertEqual(WellnessConsultation.objects.count(), 1)

    def test_email_is_required_when_contact_method_is_email(self):
        response = self.client.post('/', consultation_data(email='', preferred_contact_method='email'))

        self.assertEqual(WellnessConsultation.objects.count(), 0)
        self.assertContains(response, 'Add an email address to be contacted by email.')

    def test_booking_popup_follows_the_same_rule(self):
        service = Service.objects.filter(is_published=True).first()
        data = {
            'form_type': 'book', 'book-service': service.pk, 'book-full_name': 'Asha R',
            'book-mobile_number': '+91 90000 00002', 'book-email': '', 'book-goal': 'weight-loss',
            'book-consultation_mode': 'online', 'book-preferred_contact_method': 'email', 'book-consent': 'on',
        }
        response = self.client.post('/', data)
        self.assertEqual(WellnessConsultation.objects.count(), 0)
        self.assertContains(response, 'data-open-on-load')

        data['book-preferred_contact_method'] = 'phone'
        self.client.post('/', data)
        self.assertEqual(WellnessConsultation.objects.count(), 1)


class ServiceBookingAdminTests(TestCase):
    def setUp(self):
        self.client.force_login(get_user_model().objects.create_superuser('coach', 'coach@example.com', 'pass'))
        self.service = Service.objects.filter(is_published=True).first()
        self.booking = WellnessConsultation.objects.create(
            full_name='Booked Via Card', mobile_number='+91 90000 00011', goal='weight-loss',
            preferred_contact_method='phone', consent=True, service=self.service, source='service',
        )
        self.consultation = WellnessConsultation.objects.create(
            full_name='Free Form Person', mobile_number='+91 90000 00012', goal='energy-fitness',
            preferred_contact_method='phone', consent=True,
        )

    def test_service_bookings_have_their_own_admin_page(self):
        bookings = self.client.get('/admin/baggi/servicebooking/')
        consultations = self.client.get('/admin/baggi/wellnessconsultation/')

        self.assertContains(bookings, 'Booked Via Card')
        self.assertNotContains(bookings, 'Free Form Person')
        self.assertContains(consultations, 'Free Form Person')
        self.assertNotContains(consultations, 'Booked Via Card')
        self.assertEqual(self.client.get(f'/admin/baggi/servicebooking/{self.booking.pk}/change/').status_code, 200)

    def test_sidebar_and_dashboard_show_service_bookings(self):
        dashboard = self.client.get('/admin/')

        self.assertContains(dashboard, 'href="/admin/baggi/servicebooking/"')
        self.assertContains(dashboard, 'New service bookings')
        self.assertContains(dashboard, f'href="/admin/baggi/servicebooking/{self.booking.pk}/change/"')
        self.assertContains(dashboard, f'href="/admin/baggi/wellnessconsultation/{self.consultation.pk}/change/"')

    def test_service_badge_clears_after_visit(self):
        link = 'href="/admin/baggi/servicebooking/"'
        dashboard = self.client.get('/admin/').content.decode()
        nav_item = dashboard[dashboard.index(link):dashboard.index('</a>', dashboard.index(link))]
        self.assertIn('cw-badge', nav_item)

        self.client.get('/admin/baggi/servicebooking/')
        dashboard = self.client.get('/admin/').content.decode()
        nav_item = dashboard[dashboard.index(link):dashboard.index('</a>', dashboard.index(link))]
        self.assertNotIn('cw-badge', nav_item)


class EventRegistrationDetailsTests(TestCase):
    def test_online_event_needs_email_and_shows_online_note(self):
        event = make_event(is_online=True)
        response = self.client.post('/', registration_data(event, email=''))

        self.assertEqual(EventRegistration.objects.count(), 0)
        self.assertContains(response, 'This field is required.')
        self.assertContains(response, 'We’ll send the joining link to your email')

    def test_in_person_event_email_is_optional(self):
        event = make_event(is_online=False, venue='Community Hall, Anna Nagar')
        self.assertContains(self.client.get('/'), 'Community Hall, Anna Nagar')

        self.client.post('/', registration_data(event, email=''))

        registration = EventRegistration.objects.get()
        self.assertEqual((registration.area_city, registration.preferred_contact_method), ('Chennai', 'whatsapp'))

    def test_area_and_contact_method_are_required(self):
        event = make_event(is_online=False)
        self.client.post('/', registration_data(event, area_city='', preferred_contact_method=''))

        self.assertEqual(EventRegistration.objects.count(), 0)


class MainGoalChoicesTests(TestCase):
    def test_main_goal_offers_the_coach_list(self):
        content = self.client.get('/').content.decode()
        for label in [
            'Weight loss', 'Weight gain', 'PCOD / PCOS', 'Hormonal balance', 'Diabetes management',
            'Energy &amp; fitness', 'Lifestyle guidance', 'Children’s health', 'Women’s health', 'Men’s health',
        ]:
            self.assertIn(f'>{label}</option>', content)
        self.assertNotIn('>Something else</option>', content)


class SiteNameTests(TestCase):
    def test_pages_use_the_consultancy_name(self):
        for url in ('/', '/privacy/', '/admin/login/'):
            content = self.client.get(url).content.decode()
            self.assertIn('Geetha’s Wellness Consultancy', content, url)
            self.assertNotIn('Community Wellness', content, url)
