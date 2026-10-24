
from rest_framework import serializers

from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):

    username = serializers.CharField(
        source='user.username',
        read_only=True,
        allow_null=True
    )

    class Meta:
        model = AuditLog

        fields = [
            'log_id',
            'user',
            'username',
            'action',
            'entity_name',
            'entity_id',
            'created_at',
        ]

        read_only_fields = [
            'log_id',
            'user',
            'username',
            'action',
            'entity_name',
            'entity_id',
            'created_at',
        ]
