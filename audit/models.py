
from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    log_id = models.AutoField(primary_key=True)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs'
    )

    action = models.CharField(
        max_length=100
    )

    entity_name = models.CharField(
        max_length=100
    )

    entity_id = models.PositiveIntegerField(
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = ['-created_at', '-log_id']

    def __str__(self):
        return (
            f"{self.action} - "
            f"{self.entity_name} ({self.entity_id})"
        )
