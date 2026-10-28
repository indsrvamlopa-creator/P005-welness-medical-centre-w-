import re

from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.utils import timezone

from .models import (
    CommunityInterest,
    EventRegistration,
    Review,
    Service,
    WellnessConsultation,
)


def validate_mobile_number(value):
    RegexValidator(
        regex=r'^[+()\d\s.-]{7,30}$',
        message='Enter a valid mobile number using common phone symbols.',
    )(value)
    if sum(character.isdigit() for character in value) < 7:
        raise ValidationError('Enter a mobile number with at least 7 digits.')


mobile_number_validator = validate_mobile_number


class EventRegistrationForm(forms.ModelForm):
    mobile_number = forms.CharField(
        max_length=30,
        validators=[mobile_number_validator],
        widget=forms.TextInput(attrs={
            'type': 'tel',
            'autocomplete': 'tel',
            'placeholder': 'Your mobile number',
        }),
    )
    consent = forms.BooleanField(
        required=True,
        label='I have read the privacy notice and agree to be contacted about this request.',
    )

    class Meta:
        model = EventRegistration
        fields = [
            'full_name',
            'mobile_number',
            'email',
            'area_city',
            'preferred_contact_method',
            'event',
            'attendees',
            'message',
            'consent',
        ]
        widgets = {
            'full_name': forms.TextInput(attrs={
                'autocomplete': 'name',
                'placeholder': 'Your full name',
            }),
            'email': forms.EmailInput(attrs={
                'autocomplete': 'email',
                'placeholder': 'you@example.com',
            }),
            'area_city': forms.TextInput(attrs={
                'autocomplete': 'address-level2',
                'placeholder': 'Your area or city',
            }),
            'message': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Optional question or message',
            }),
        }

    def __init__(self, *args, events, hide_event=False, **kwargs):
        """`events` should contain only events that are open for registration.

        With `hide_event`, the event is fixed by `initial` and sent as a hidden field.
        """
        super().__init__(*args, **kwargs)
        self.fields['event'].queryset = events
        self.fields['event'].empty_label = 'Choose an event'
        self.fields['event'].label_from_instance = lambda event: (
            f'{event.title} — {timezone.localtime(event.starts_at):%d %b %Y, %I:%M %p}'
        )
        self.fields['attendees'].required = False
        self.fields['attendees'].widget.attrs.update({'min': 1, 'max': 10})
        self.fields['area_city'].required = True
        self.fields['preferred_contact_method'].required = True
        # Online events need an email address to send the joining link.
        event = events.filter(pk=self.initial.get('event') or None).first() if hide_event else None
        self.event_is_online = bool(event and event.is_online)
        self.fields['email'].required = self.event_is_online
        if self.event_is_online:
            self.fields['email'].widget.attrs['data-always-required'] = ''
        if not self.event_is_online:
            self.fields['email'].widget.attrs['placeholder'] = 'you@example.com (optional)'
        if hide_event:
            self.fields['event'].widget = forms.HiddenInput()
            return
        event_count = events.count()
        self.fields['event'].required = event_count > 0
        if event_count <= 1:
            self.fields['event'].widget = forms.HiddenInput()
            if event_count == 1:
                self.initial['event'] = events.first()

    def clean_attendees(self):
        return self.cleaned_data.get('attendees') or 1

    def clean(self):
        cleaned_data = super().clean()
        event = cleaned_data.get('event')
        attendees = cleaned_data.get('attendees')
        mobile_number = cleaned_data.get('mobile_number')
        if not event:
            return cleaned_data
        if event.is_online and not cleaned_data.get('email') and 'email' not in self.errors:
            self.add_error('email', 'Add your email so we can send you the joining link.')
        if cleaned_data.get('preferred_contact_method') == 'email' and not cleaned_data.get('email'):
            if 'email' not in self.errors:
                self.add_error('email', 'Add an email address to be contacted by email.')

        # Re-check against the database in case the event filled up or closed meanwhile.
        status = event.registration_status
        if status != 'open':
            raise ValidationError(
                'Sorry, this event is fully booked.' if status == 'full'
                else 'Sorry, registration for this event has closed.'
            )
        seats_left = event.seats_left
        if attendees and seats_left is not None and attendees > seats_left:
            self.add_error('attendees', f'Only {seats_left} place(s) left for this event.')

        if mobile_number:
            digits = re.sub(r'\D', '', mobile_number)
            already_registered = any(
                re.sub(r'\D', '', existing) == digits
                for existing in event.registrations.values_list('mobile_number', flat=True)
            )
            if already_registered:
                self.add_error('mobile_number', 'This mobile number is already registered for this event.')
        return cleaned_data


class CommunityInterestForm(forms.ModelForm):
    mobile_number = forms.CharField(
        max_length=30,
        validators=[mobile_number_validator],
        widget=forms.TextInput(attrs={
            'type': 'tel',
            'autocomplete': 'tel',
            'placeholder': 'Your mobile number',
        }),
    )
    consent = forms.BooleanField(
        required=True,
        label='I have read the privacy notice and agree to this enquiry being handled and followed up.',
    )

    class Meta:
        model = CommunityInterest
        fields = [
            'full_name',
            'mobile_number',
            'email',
            'area_city',
            'area_of_interest',
            'preferred_contact_method',
            'message',
            'consent',
        ]
        widgets = {
            'full_name': forms.TextInput(attrs={
                'autocomplete': 'name',
                'placeholder': 'Your full name',
            }),
            'email': forms.EmailInput(attrs={
                'autocomplete': 'email',
                'placeholder': 'you@example.com (optional)',
            }),
            'area_city': forms.TextInput(attrs={
                'autocomplete': 'address-level2',
                'placeholder': 'Your area or city (optional)',
            }),
            'message': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Optional message. Please do not include medical or other sensitive information.',
            }),
        }

    def clean(self):
        cleaned_data = super().clean()
        if (
            cleaned_data.get('preferred_contact_method') == 'email'
            and not cleaned_data.get('email')
        ):
            self.add_error('email', 'Add an email address to be contacted by email.')
        return cleaned_data


class WellnessConsultationForm(forms.ModelForm):
    mobile_number = forms.CharField(
        max_length=30,
        validators=[mobile_number_validator],
        widget=forms.TextInput(attrs={
            'type': 'tel',
            'autocomplete': 'tel',
            'placeholder': 'Your mobile number',
        }),
    )
    preferred_at = forms.DateTimeField(
        label='Preferred date & time',
        required=False,
        input_formats=['%Y-%m-%dT%H:%M'],
        widget=forms.DateTimeInput(
            format='%Y-%m-%dT%H:%M',
            attrs={'type': 'datetime-local'},
        ),
    )
    consent = forms.BooleanField(
        required=True,
        label='I have read the privacy notice and agree to be contacted about my free consultation.',
    )

    class Meta:
        model = WellnessConsultation
        fields = [
            'full_name',
            'mobile_number',
            'email',
            'area_city',
            'service',
            'goal',
            'consultation_mode',
            'preferred_at',
            'preferred_contact_method',
            'message',
            'consent',
        ]
        widgets = {
            'full_name': forms.TextInput(attrs={
                'autocomplete': 'name',
                'placeholder': 'Your full name',
            }),
            'email': forms.EmailInput(attrs={
                'autocomplete': 'email',
                'placeholder': 'you@example.com (optional)',
            }),
            'area_city': forms.TextInput(attrs={
                'autocomplete': 'address-level2',
                'placeholder': 'Your area or city (optional)',
            }),
            'message': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Optional: anything you would like the coach to know. Please do not share medical history.',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['service'].queryset = Service.objects.filter(is_published=True)
        self.fields['service'].empty_label = 'Not sure yet'

    def clean(self):
        cleaned_data = super().clean()
        if (
            cleaned_data.get('preferred_contact_method') == 'email'
            and not cleaned_data.get('email')
        ):
            self.add_error('email', 'Add an email address to be contacted by email.')
        return cleaned_data


class ReviewForm(forms.ModelForm):
    # Hidden from people; bots that fill every field are rejected.
    website = forms.CharField(required=False, label='Leave this empty')
    rating = forms.TypedChoiceField(
        choices=[(n, n) for n in range(5, 0, -1)],
        coerce=int,
        widget=forms.RadioSelect,
        error_messages={'required': 'Please choose a star rating.'},
    )
    consent_to_publish = forms.BooleanField(
        required=True,
        label='I agree to my name, rating and review being shown on this website.',
    )

    class Meta:
        model = Review
        fields = ['full_name', 'service', 'rating', 'review', 'area_city', 'consent_to_publish']
        widgets = {
            'full_name': forms.TextInput(attrs={
                'autocomplete': 'given-name',
                'placeholder': 'First name or initials',
            }),
            'area_city': forms.TextInput(attrs={'placeholder': 'e.g. Chennai (optional)'}),
            'review': forms.Textarea(attrs={
                'rows': 4,
                'maxlength': 600,
                'placeholder': 'How has the coaching helped you? Please do not share medical details.',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['service'].queryset = Service.objects.filter(is_published=True)
        self.fields['service'].empty_label = 'General coaching'

    def clean_website(self):
        if self.cleaned_data.get('website'):
            raise ValidationError('Your review could not be sent. Please try again.')
        return ''

    def clean_review(self):
        review = self.cleaned_data['review'].strip()
        if len(review) < 10:
            raise ValidationError('Please write at least a short sentence.')
        return review
