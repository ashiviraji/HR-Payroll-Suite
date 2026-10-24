
from django.contrib import admin

from .models import Notification


# =========================================================
# NOTIFICATION ADMIN CONFIGURATION
# =========================================================

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):

    # Columns displayed in Django Admin
    list_display = (
        'notification_id',
        'recipient',
        'notification_type',
        'title',
        'is_read',
        'created_at',
    )

    # Filter notifications
    list_filter = (
        'notification_type',
        'is_read',
        'created_at',
    )

    # Search notifications
    search_fields = (
        'title',
        'message',
    )

    # Default ordering
    ordering = (
        '-created_at',
    )

    # Fields that cannot be edited
    readonly_fields = (
        'created_at',
        'read_at',
    )
