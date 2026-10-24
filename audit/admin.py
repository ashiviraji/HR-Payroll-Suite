from django.contrib import admin
from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = (
        'log_id',
        'user',
        'action',
        'entity_name',
        'entity_id',
        'created_at',
    )

    list_filter = (
        'action',
        'entity_name',
        'created_at',
    )

    search_fields = (
        'user__username',
        'action',
        'entity_name',
    )

    readonly_fields = (
        'user',
        'action',
        'entity_name',
        'entity_id',
        'created_at',
    )