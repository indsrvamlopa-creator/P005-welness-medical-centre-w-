from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.utils import timezone


MAX_IMAGE_SIZE_MB = 5


def validate_image_size(image):
    if image.size > MAX_IMAGE_SIZE_MB * 1024 * 1024:
        raise ValidationError(f'Please upload an image smaller than {MAX_IMAGE_SIZE_MB} MB.')


class CommunityEventQuerySet(models.QuerySet):
    def upcoming(self):
        return self.filter(is_published=True, starts_at__gte=timezone.now()).annotate(
            seats_taken=Coalesce(Sum('registrations__attendees'), 0),
        )


class CommunityEvent(models.Model):
    title = models.CharField(max_length=160)
    description = models.TextField()
    image = models.ImageField(
        upload_to='events/%Y/%m/',
        blank=True,
        validators=[
            FileExtensionValidator(['jpg', 'jpeg', 'png', 'webp']),
            validate_image_size,
        ],
        help_text='Optional. JPG, PNG or WebP, up to 5 MB. A wide (landscape) photo looks best.',
    )
    starts_at = models.DateTimeField('starts at')
    ends_at = models.DateTimeField('ends at', null=True, blank=True)
    venue = models.CharField(max_length=200, blank=True)
    is_online = models.BooleanField(default=False)
    is_published = models.BooleanField(default=False, help_text='Show this event on the website.')
    registration_open = models.BooleanField(
        default=True,
        help_text='Untick to stop accepting registrations while keeping the event visible.',
    )
    registration_closes_at = models.DateTimeField(
        'registration closes at',
        null=True,
        blank=True,
        help_text='Leave blank to accept registrations until the event starts.',
    )
    capacity = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='Maximum number of people. Leave blank for no limit.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = CommunityEventQuerySet.as_manager()

    class Meta:
        ordering = ['starts_at']
        verbose_name = 'event or wellness session'
        verbose_name_plural = 'events and wellness sessions'

    def __str__(self):
        return f'{self.title} — {timezone.localtime(self.starts_at):%Y-%m-%d %H:%M}'

    def clean(self):
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValidationError({'ends_at': 'The end time must be after the start time.'})
        if (
            self.starts_at
            and self.registration_closes_at
            and self.registration_closes_at > self.starts_at
        ):
            raise ValidationError({
                'registration_closes_at': 'Registration must close before the event starts.',
            })

    def get_seats_taken(self):
        if hasattr(self, 'seats_taken'):
            return self.seats_taken
        return self.registrations.aggregate(total=Coalesce(Sum('attendees'), 0))['total']

    @property
    def seats_left(self):
        if self.capacity is None:
            return None
        return max(self.capacity - self.get_seats_taken(), 0)

    @property
    def registration_status(self):
        """One of 'open', 'full' or 'closed'."""
        now = timezone.now()
        closes_at = self.registration_closes_at or self.starts_at
        if not self.registration_open or now >= closes_at:
            return 'closed'
        if self.seats_left == 0:
            return 'full'
        return 'open'


class EventRegistration(models.Model):
    CONTACT_METHOD_CHOICES = [
        ('whatsapp', 'WhatsApp'),
        ('phone', 'Phone'),
        ('email', 'Email'),
    ]

    full_name = models.CharField(max_length=150)
    mobile_number = models.CharField(max_length=30)
    email = models.EmailField(blank=True)
    area_city = models.CharField('area / city', max_length=120, blank=True)
    preferred_contact_method = models.CharField(max_length=10, choices=CONTACT_METHOD_CHOICES, blank=True)
    event = models.ForeignKey(
        CommunityEvent,
        on_delete=models.PROTECT,
        related_name='registrations',
    )
    attendees = models.PositiveSmallIntegerField(
        'number of people (including you)',
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
    )
    preferred_at = models.DateTimeField(null=True, blank=True)
    message = models.TextField(blank=True)
    consent = models.BooleanField(default=False)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-submitted_at']

    def __str__(self):
        return f'{self.full_name} — {self.event.title}'


class CommunityInterest(models.Model):
    INTEREST_CHOICES = [
        ('wellness-sessions', 'Wellness sessions'),
        ('community-activities', 'Community activities'),
        ('general-information', 'General information'),
        ('team-opportunity', 'Team opportunity'),
    ]
    CONTACT_METHOD_CHOICES = [
        ('whatsapp', 'WhatsApp'),
        ('phone', 'Phone'),
        ('email', 'Email'),
    ]

    full_name = models.CharField(max_length=150)
    mobile_number = models.CharField(max_length=30)
    email = models.EmailField(blank=True)
    area_city = models.CharField(max_length=120, blank=True)
    area_of_interest = models.CharField(max_length=32, choices=INTEREST_CHOICES)
    preferred_contact_method = models.CharField(
        max_length=10,
        choices=CONTACT_METHOD_CHOICES,
    )
    message = models.TextField(blank=True)
    consent = models.BooleanField(default=False)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-submitted_at']

    def __str__(self):
        return f'{self.full_name} — {self.get_area_of_interest_display()}'


def format_inr(amount):
    """Format a Decimal in Indian digit grouping, e.g. 125000 -> '1,25,000'."""
    whole, _, paise = f'{amount:.2f}'.partition('.')
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        whole = ','.join(([head] if head else []) + groups + [tail])
    return whole if paise == '00' else f'{whole}.{paise}'


class Service(models.Model):
    ICON_CHOICES = [
        ('✳', '✳ Star burst'),
        ('↗', '↗ Arrow (progress)'),
        ('◌', '◌ Circle (balance)'),
        ('✦', '✦ Sparkle'),
        ('❋', '❋ Flower'),
        ('♡', '♡ Heart'),
        ('☀', '☀ Sun (energy)'),
        ('◆', '◆ Diamond (premium)'),
        ('✚', '✚ Plus (health)'),
        ('❖', '❖ Pattern'),
    ]
    PRICE_UNIT_CHOICES = [
        ('', 'One-time'),
        ('per session', 'Per session'),
        ('per week', 'Per week'),
        ('per month', 'Per month'),
        ('per 3 months', 'Per 3 months'),
        ('per programme', 'Per programme'),
    ]

    title = models.CharField(max_length=120)
    slug = models.SlugField(max_length=60, unique=True, help_text='Filled in automatically from the title.')
    summary = models.TextField(max_length=300)
    icon = models.CharField(max_length=4, choices=ICON_CHOICES, default='✳')
    price = models.DecimalField(
        'price (₹)',
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text='Leave blank to hide the price. Enter 0 to show “Free”.',
    )
    original_price = models.DecimalField(
        'original price (₹)',
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text='Optional. Shown crossed out next to the price, for offers.',
    )
    price_unit = models.CharField(max_length=20, choices=PRICE_UNIT_CHOICES, blank=True)
    display_order = models.PositiveSmallIntegerField(default=0, help_text='Lower numbers appear first.')
    is_published = models.BooleanField(default=True, help_text='Show this service on the website.')

    class Meta:
        ordering = ['display_order', 'title']

    def __str__(self):
        return self.title

    def clean(self):
        if (
            self.price is not None
            and self.original_price is not None
            and self.original_price <= self.price
        ):
            raise ValidationError({'original_price': 'The original price should be higher than the price.'})

    @property
    def is_free(self):
        return self.price is not None and self.price == 0

    @property
    def price_display(self):
        return None if self.price is None else format_inr(self.price)

    @property
    def original_price_display(self):
        if self.original_price is None or self.price is None or self.original_price <= self.price:
            return None
        return format_inr(self.original_price)


class WellnessConsultation(models.Model):
    GOAL_CHOICES = [
        ('weight-loss', 'Weight loss'),
        ('weight-gain', 'Weight gain'),
        ('pcod-pcos', 'PCOD / PCOS'),
        ('hormonal-balance', 'Hormonal balance'),
        ('diabetes', 'Diabetes management'),
        ('energy-fitness', 'Energy & fitness'),
        ('healthy-lifestyle', 'Lifestyle guidance'),
        ('children', 'Children’s health'),
        ('women', 'Women’s health'),
        ('men', 'Men’s health'),
    ]
    MODE_CHOICES = [
        ('in-person', 'In person'),
        ('online', 'Online video call'),
        ('phone', 'Phone call'),
    ]
    CONTACT_METHOD_CHOICES = CommunityInterest.CONTACT_METHOD_CHOICES
    STATUS_CHOICES = [
        ('new', 'New'),
        ('contacted', 'Contacted'),
        ('scheduled', 'Consultation scheduled'),
        ('completed', 'Completed'),
        ('closed', 'Closed'),
    ]
    SOURCE_CHOICES = [
        ('consultation', 'Free consultation form'),
        ('service', 'Service booking ("Book this")'),
    ]

    full_name = models.CharField(max_length=150)
    mobile_number = models.CharField(max_length=30)
    email = models.EmailField(blank=True)
    area_city = models.CharField(max_length=120, blank=True)
    service = models.ForeignKey(
        Service,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='consultations',
        verbose_name='service you are interested in',
    )
    goal = models.CharField('main goal', max_length=32, choices=GOAL_CHOICES)
    consultation_mode = models.CharField(max_length=10, choices=MODE_CHOICES, default='online')
    preferred_at = models.DateTimeField('preferred date & time', null=True, blank=True)
    preferred_contact_method = models.CharField(max_length=10, choices=CONTACT_METHOD_CHOICES)
    message = models.TextField(blank=True)
    consent = models.BooleanField(default=False)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='new')
    source = models.CharField(
        'submitted from',
        max_length=12,
        choices=SOURCE_CHOICES,
        default='consultation',
        help_text='Which website form this came from.',
    )
    coach_notes = models.TextField(blank=True, help_text='Private notes, never shown on the website.')
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-submitted_at']
        verbose_name = 'wellness consultation request'

    def __str__(self):
        return f'{self.full_name} — {self.get_goal_display()}'


class ServiceBooking(WellnessConsultation):
    """Bookings made with "Book this" on a service card; same table, own admin page."""

    class Meta:
        proxy = True
        verbose_name = 'service booking'


class SuccessStory(models.Model):
    client_name = models.CharField(max_length=80, help_text='First name or initials only, with the client’s permission.')
    quote = models.TextField(max_length=400)
    client_consent = models.BooleanField(
        default=False,
        help_text='Tick only when the client has agreed to this story being published.',
    )
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'success stories'

    def __str__(self):
        return self.client_name


class Review(models.Model):
    RATING_CHOICES = [(n, f'{n} star{"s" if n > 1 else ""}') for n in range(5, 0, -1)]

    full_name = models.CharField('your name', max_length=80, help_text='Shown on the website.')
    service = models.ForeignKey(
        Service,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviews',
        verbose_name='service you used',
    )
    rating = models.PositiveSmallIntegerField(
        choices=RATING_CHOICES,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    review = models.TextField('your review', max_length=600)
    area_city = models.CharField('area or city', max_length=80, blank=True)
    before_photo = models.ImageField(
        upload_to='reviews/%Y/%m/',
        blank=True,
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png', 'webp']), validate_image_size],
        help_text='Optional. Only add with the client’s written permission. JPG, PNG or WebP, up to 5 MB.',
    )
    after_photo = models.ImageField(
        upload_to='reviews/%Y/%m/',
        blank=True,
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png', 'webp']), validate_image_size],
        help_text='Optional. Portrait photos taken in similar light and pose compare best.',
    )
    consent_to_publish = models.BooleanField(default=False)
    is_approved = models.BooleanField(
        'approved for website',
        default=False,
        help_text='Only approved reviews are shown. Check the review makes no medical or guaranteed-result claims.',
    )
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-submitted_at']

    def __str__(self):
        return f'{self.full_name} — {self.rating}★'

    @property
    def initial(self):
        return self.full_name.strip()[:1].upper()


class SiteSettings(models.Model):
    """One row of contact details and social links, edited in the admin."""

    whatsapp_number = models.CharField(
        max_length=30,
        blank=True,
        help_text='With country code, e.g. +91 98765 43210. Powers the floating WhatsApp button.',
    )
    whatsapp_message = models.CharField(
        max_length=200,
        blank=True,
        default='Hi! I found your website and would like to know more about a free wellness consultation.',
        help_text='Pre-filled text when a visitor opens the WhatsApp chat.',
    )
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    facebook_url = models.URLField('Facebook', blank=True)
    instagram_url = models.URLField('Instagram', blank=True)
    youtube_url = models.URLField('YouTube', blank=True)
    x_url = models.URLField('X (Twitter)', blank=True)
    linkedin_url = models.URLField('LinkedIn', blank=True)
    telegram_url = models.URLField('Telegram', blank=True)

    class Meta:
        verbose_name = 'site settings'
        verbose_name_plural = 'site settings'

    def __str__(self):
        return 'Contact details & social media'

    def save(self, *args, **kwargs):
        self.pk = 1  # Only ever one settings row.
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        return cls.objects.get_or_create(pk=1)[0]

    @property
    def social_links(self):
        """(key, label, url) for each network that has a link."""
        networks = [
            ('facebook', 'Facebook', self.facebook_url),
            ('instagram', 'Instagram', self.instagram_url),
            ('youtube', 'YouTube', self.youtube_url),
            ('x', 'X', self.x_url),
            ('linkedin', 'LinkedIn', self.linkedin_url),
            ('telegram', 'Telegram', self.telegram_url),
        ]
        return [(key, label, url) for key, label, url in networks if url]


class AboutPhoto(models.Model):
    """A photo in the About section slideshow."""

    image = models.ImageField(
        upload_to='about/',
        validators=[
            FileExtensionValidator(['jpg', 'jpeg', 'png', 'webp']),
            validate_image_size,
        ],
        help_text='JPG, PNG or WebP, up to 5 MB. A tall (portrait) photo looks best.',
    )
    alt_text = models.CharField(
        'description',
        max_length=160,
        help_text='What the photo shows, e.g. "Group stretching class". Read aloud by screen readers.',
    )
    sort_order = models.PositiveIntegerField('order', default=0, help_text='Lower numbers show first.')
    is_published = models.BooleanField(default=True, help_text='Show this photo on the website.')

    class Meta:
        ordering = ('sort_order', 'pk')
        verbose_name = 'about photo'

    def __str__(self):
        return self.alt_text


class AdminPageVisit(models.Model):
    """When each admin last opened a list page, so sidebar badges only count newer items."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='+')
    page = models.CharField(max_length=60)
    visited_at = models.DateTimeField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'page'], name='unique_admin_page_visit')]

    def __str__(self):
        return f'{self.user} — {self.page}'
