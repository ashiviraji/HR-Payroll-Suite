
from django.conf import settings
from django.db import models
from django.utils import timezone


# =========================================================
# NOTIFICATION MODEL
# =========================================================

class Notification(models.Model):

    NOTIFICATION_TYPES = [
        ('PAYROLL', 'Payroll'),
        ('LEAVE', 'Leave Management'),
        ('PERFORMANCE', 'Performance'),
        ('SYSTEM', 'System'),
    ]

    notification_id = models.AutoField(
        primary_key=True
    )

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications'
    )

    notification_type = models.CharField(
        max_length=20,
        choices=NOTIFICATION_TYPES,
        default='SYSTEM'
    )

    title = models.CharField(
        max_length=200
    )

    message = models.TextField()

    is_read = models.BooleanField(
        default=False
    )

    created_at = models.DateTimeField(
        default=timezone.now
    )

    read_at = models.DateTimeField(
        null=True,
        blank=True
    )

    # Optional reference to the related record
    related_entity = models.CharField(
        max_length=50,
        blank=True
    )

    related_entity_id = models.PositiveIntegerField(
        null=True,
        blank=True
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return (
            f"{self.title} - "
            f"{self.recipient}"
        )
