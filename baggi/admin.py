import csv

from django.contrib import admin
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils import timezone

from .models import (
    AdminPageVisit,
    AboutPhoto,
    CommunityEvent,
    CommunityInterest,
    EventRegistration,
    Review,
    Service,
    ServiceBooking,
    SiteSettings,
    SuccessStory,
    WellnessConsultation,
)


EDIT_ICON = mark_safe(
    '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" '
    'stroke-linecap="round" stroke-linejoin="round"><path d="M4 20h4L19 9l-4-4L4 16z"/><path d="m13.5 6.5 4 4"/></svg>'
)
DELETE_ICON = mark_safe(
    '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" '
    'stroke-linecap="round" stroke-linejoin="round"><path d="M4.5 7h15M9.5 7V4.5h5V7M6.5 7l1 13h9l1-13M10 11v5.5M14 11v5.5"/></svg>'
)


class RowActionsAdmin(admin.ModelAdmin):
    """Adds Edit and Delete icon buttons at the start of every row of the list page."""

    def get_list_display(self, request):
        return ('row_actions', *super().get_list_display(request))

    def get_list_display_links(self, request, list_display):
        # By default Django links the first column; keep that link on the first real field.
        if not self.list_display_links and self.list_display_links is not None:
            return list(list_display)[1:2]
        return super().get_list_display_links(request, list_display)

    @admin.display(description='Actions')
    def row_actions(self, obj):
        opts = obj._meta
        url_name = f'admin:{opts.app_label}_{opts.model_name}'
        return format_html(
            '<span class="row-actions">'
            '<a class="row-action row-edit" href="{}" title="Edit" aria-label="Edit {}">{}</a>'
            '<a class="row-action row-delete" href="{}" title="Delete" aria-label="Delete {}">{}</a>'
            '</span>',
            reverse(f'{url_name}_change', args=[obj.pk]),
            obj,
            EDIT_ICON,
            reverse(f'{url_name}_delete', args=[obj.pk]),
            obj,
            DELETE_ICON,
        )


@admin.action(description='Export selected rows to CSV (Excel)')
def export_as_csv(modeladmin, request, queryset):
    fields = [field for field in queryset.model._meta.fields if field.name != 'coach_notes']
    filename = f'{queryset.model._meta.model_name}-{timezone.localdate():%Y-%m-%d}.csv'
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response.write('﻿')  # Lets Excel detect UTF-8.
    writer = csv.writer(response)
    writer.writerow([field.verbose_name.capitalize() for field in fields])
    for obj in queryset:
        row = []
        for field in fields:
            display = getattr(obj, f'get_{field.name}_display', None)
            row.append(display() if display else getattr(obj, field.name))
        writer.writerow(row)
    return response


@admin.register(Service)
class ServiceAdmin(RowActionsAdmin):
    list_display = ('icon', 'title', 'price', 'original_price', 'price_unit', 'display_order', 'is_published')
    list_display_links = ('icon', 'title')
    list_editable = ('price', 'original_price', 'price_unit', 'display_order', 'is_published')
    search_fields = ('title', 'summary')
    prepopulated_fields = {'slug': ('title',)}
    fieldsets = (
        ('Service card', {'fields': ('title', 'slug', 'icon', 'summary')}),
        ('Price', {
            'fields': ('price', 'original_price', 'price_unit'),
            'description': 'Shown on the service card. Leave the price blank to hide it.',
        }),
        ('Website', {'fields': ('display_order', 'is_published')}),
    )


@admin.register(WellnessConsultation)
class WellnessConsultationAdmin(RowActionsAdmin):
    list_display = (
        'full_name',
        'mobile_number',
        'goal',
        'service',
        'consultation_mode',
        'preferred_at',
        'status',
        'submitted_at',
    )
    list_editable = ('status',)
    list_filter = ('status', 'goal', 'service', 'consultation_mode', 'submitted_at')
    search_fields = ('full_name', 'mobile_number', 'email', 'area_city')
    readonly_fields = ('submitted_at',)
    actions = [export_as_csv]

    source = 'consultation'

    def get_queryset(self, request):
        return super().get_queryset(request).filter(source=self.source)

    def changelist_view(self, request, extra_context=None):
        # Opening this list clears the sidebar's "new" badge for this admin.
        AdminPageVisit.objects.update_or_create(
            user=request.user, page=self.model._meta.model_name, defaults={'visited_at': timezone.now()},
        )
        return super().changelist_view(request, extra_context)


@admin.register(ServiceBooking)
class ServiceBookingAdmin(WellnessConsultationAdmin):
    """Bookings made with "Book this" on the website's service cards."""

    source = 'service'
    list_display = (
        'full_name',
        'service',
        'mobile_number',
        'email',
        'preferred_contact_method',
        'preferred_at',
        'status',
        'submitted_at',
    )
    list_filter = ('status', 'service', 'preferred_contact_method', 'submitted_at')

    def save_model(self, request, obj, form, change):
        obj.source = 'service'
        super().save_model(request, obj, form, change)


@admin.register(SuccessStory)
class SuccessStoryAdmin(RowActionsAdmin):
    list_display = ('client_name', 'client_consent', 'is_published', 'created_at')
    list_editable = ('is_published',)
    list_filter = ('is_published',)


class EventRegistrationInline(admin.TabularInline):
    model = EventRegistration
    fields = ('full_name', 'mobile_number', 'email', 'attendees', 'message', 'consent', 'submitted_at')
    readonly_fields = ('submitted_at',)
    extra = 0
    show_change_link = True


@admin.register(CommunityEvent)
class CommunityEventAdmin(RowActionsAdmin):
    list_display = (
        'thumbnail',
        'title',
        'starts_at',
        'ends_at',
        'venue',
        'is_online',
        'is_published',
        'registration_open',
        'seats',
        'registration_state',
    )
    list_filter = ('is_published', 'registration_open', 'is_online', 'starts_at')
    search_fields = ('title', 'description', 'venue')
    list_editable = ('is_published', 'registration_open')
    ordering = ('starts_at',)
    date_hierarchy = 'starts_at'
    fieldsets = (
        ('Event details', {'fields': ('title', 'description', 'image', 'image_preview')}),
        ('Date, time & venue', {'fields': ('starts_at', 'ends_at', 'is_online', 'venue')}),
        ('Registration', {'fields': ('registration_open', 'registration_closes_at', 'capacity')}),
        ('Website', {'fields': ('is_published',)}),
    )
    list_display_links = ('thumbnail', 'title')
    readonly_fields = ('image_preview',)
    inlines = [EventRegistrationInline]

    @admin.display(description='Current image')
    def image_preview(self, obj):
        if not obj or not obj.image:
            return 'No image uploaded yet.'
        return format_html(
            '<img src="{}" alt="" style="max-width:320px;max-height:180px;object-fit:cover">',
            obj.image.url,
        )

    @admin.display(description='Image')
    def thumbnail(self, obj):
        if not obj.image:
            return '—'
        return format_html(
            '<img src="{}" alt="" style="width:64px;height:40px;object-fit:cover">',
            obj.image.url,
        )

    def get_inlines(self, request, obj):
        # A brand-new event has no registrations yet.
        return self.inlines if obj else []

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            seats_taken=Coalesce(Sum('registrations__attendees'), 0),
        )

    @admin.display(description='Seats taken', ordering='seats_taken')
    def seats(self, obj):
        return f'{obj.seats_taken} / {obj.capacity}' if obj.capacity else obj.seats_taken

    @admin.display(description='Status on website')
    def registration_state(self, obj):
        if obj.starts_at < timezone.now():
            return 'Finished'
        return {'open': 'Open', 'full': 'Fully booked', 'closed': 'Closed'}[obj.registration_status]


@admin.register(EventRegistration)
class EventRegistrationAdmin(RowActionsAdmin):
    list_display = (
        'full_name',
        'mobile_number',
        'email',
        'area_city',
        'preferred_contact_method',
        'event',
        'event_mode',
        'attendees',
        'submitted_at',
    )
    list_filter = ('event', 'event__is_online', 'preferred_contact_method', 'submitted_at')
    search_fields = ('full_name', 'mobile_number', 'email', 'area_city')
    list_select_related = ('event',)

    @admin.display(description='Online / in person', ordering='event__is_online')
    def event_mode(self, obj):
        return 'Online' if obj.event.is_online else 'In person'
    readonly_fields = ('submitted_at',)
    autocomplete_fields = ('event',)
    actions = [export_as_csv]


@admin.register(CommunityInterest)
class CommunityInterestAdmin(RowActionsAdmin):
    list_display = (
        'full_name',
        'mobile_number',
        'area_of_interest',
        'preferred_contact_method',
        'submitted_at',
    )
    list_filter = ('area_of_interest', 'preferred_contact_method', 'submitted_at')
    search_fields = ('full_name', 'mobile_number', 'email', 'area_city')
    readonly_fields = ('submitted_at',)
    actions = [export_as_csv]


@admin.action(description='Approve selected reviews (show on website)')
def approve_reviews(modeladmin, request, queryset):
    updated = queryset.update(is_approved=True)
    modeladmin.message_user(request, f'{updated} review(s) approved and now shown on the website.')


@admin.action(description='Hide selected reviews from website')
def hide_reviews(modeladmin, request, queryset):
    updated = queryset.update(is_approved=False)
    modeladmin.message_user(request, f'{updated} review(s) hidden from the website.')


@admin.register(Review)
class ReviewAdmin(RowActionsAdmin):
    list_display = ('full_name', 'stars', 'service', 'short_review', 'photos', 'is_approved', 'submitted_at')
    list_editable = ('is_approved',)
    list_filter = ('is_approved', 'rating', 'service', 'submitted_at')
    search_fields = ('full_name', 'review', 'area_city')
    readonly_fields = ('submitted_at', 'photo_preview')
    actions = [approve_reviews, hide_reviews, export_as_csv]
    fieldsets = (
        ('Review', {'fields': ('full_name', 'area_city', 'service', 'rating', 'review')}),
        ('Before & after transformation', {
            'fields': ('before_photo', 'after_photo', 'photo_preview'),
            'description': 'Optional. Add photos only with the client’s written permission.',
        }),
        ('Publishing', {'fields': ('consent_to_publish', 'is_approved', 'submitted_at')}),
    )

    @admin.display(description='Current photos')
    def photo_preview(self, obj):
        if not obj or not (obj.before_photo or obj.after_photo):
            return 'No photos uploaded yet.'
        images = [
            format_html(
                '<figure style="display:inline-block;margin:0 14px 0 0;text-align:center">'
                '<img src="{}" alt="" style="width:150px;height:190px;object-fit:cover">'
                '<figcaption>{}</figcaption></figure>',
                photo.url, label,
            )
            for label, photo in (('Before', obj.before_photo), ('After', obj.after_photo)) if photo
        ]
        # Each piece is already escaped by format_html.
        return mark_safe(''.join(images))

    @admin.display(description='Photos')
    def photos(self, obj):
        images = [photo for photo in (obj.before_photo, obj.after_photo) if photo]
        if not images:
            return '—'
        return mark_safe(''.join(
            format_html('<img src="{}" alt="" style="width:34px;height:42px;object-fit:cover;margin-right:4px">', photo.url)
            for photo in images
        ))

    @admin.display(description='Rating', ordering='rating')
    def stars(self, obj):
        return format_html('<span style="color:#b8963e;letter-spacing:2px">{}</span>', '★' * obj.rating + '☆' * (5 - obj.rating))

    @admin.display(description='Review')
    def short_review(self, obj):
        return obj.review if len(obj.review) <= 70 else f'{obj.review[:70]}…'


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    """A single settings page: the list view jumps straight to the form."""

    fieldsets = (
        ('WhatsApp chat button', {
            'fields': ('whatsapp_number', 'whatsapp_message'),
            'description': 'The green chat button shows on every page. Without a number it opens the enquiry form.',
        }),
        ('Contact details (footer)', {'fields': ('phone', 'email')}),
        ('Social media (footer icons)', {
            'fields': ('facebook_url', 'instagram_url', 'youtube_url', 'x_url', 'linkedin_url', 'telegram_url'),
            'description': 'Paste the full link to each profile. Only filled-in networks are shown.',
        }),
    )

    def changelist_view(self, request, extra_context=None):
        settings_row = SiteSettings.load()
        return HttpResponseRedirect(
            reverse('admin:baggi_sitesettings_change', args=[settings_row.pk]),
        )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AboutPhoto)
class AboutPhotoAdmin(RowActionsAdmin):
    """Photos for the About section slideshow. With none published, built-in exercise photos show."""

    list_display = ('thumbnail', 'alt_text', 'sort_order', 'is_published')
    list_display_links = ('thumbnail', 'alt_text')
    list_editable = ('sort_order', 'is_published')
    fields = ('image', 'image_preview', 'alt_text', 'sort_order', 'is_published')
    readonly_fields = ('image_preview',)

    @admin.display(description='Current image')
    def image_preview(self, obj):
        if not obj or not obj.image:
            return 'No image uploaded yet.'
        return format_html(
            '<img src="{}" alt="" style="max-width:200px;max-height:250px;object-fit:cover">',
            obj.image.url,
        )

    @admin.display(description='Photo')
    def thumbnail(self, obj):
        return format_html(
            '<img src="{}" alt="" style="width:40px;height:50px;object-fit:cover">',
            obj.image.url,
        )


admin.site.site_header = 'Wellness Consultancy admin'
admin.site.site_title = 'Geetha’s Wellness Consultancy admin'
admin.site.index_title = 'Dashboard'

# The custom layout in templates/admin/ draws its own sidebar menu.
admin.site.enable_nav_sidebar = False
