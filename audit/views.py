
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied

from .models import AuditLog
from .serializers import AuditLogSerializer


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):

    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        # Superusers and HR Officers can view audit logs
        is_hr_officer = (
            user.role is not None
            and user.role.role_name == 'HR_OFFICER'
        )

        if not (user.is_superuser or is_hr_officer):
            raise PermissionDenied(
                'You do not have permission to view audit logs.'
            )

        return AuditLog.objects.select_related(
            'user'
        ).all()
