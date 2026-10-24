from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from audit.utils import create_audit_log
from .models import Role, UserAccount
from .serializers import RoleSerializer, UserAccountSerializer


def is_hr_or_admin(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    role = getattr(user, 'role', None)
    return role is not None and role.role_name == 'HR_OFFICER'


class HRAccountPermission(IsAuthenticated):
    message = 'Only HR Officers or administrators can manage accounts.'

    def has_permission(self, request, view):
        return super().has_permission(request, view) and is_hr_or_admin(request.user)


class RoleViewSet(viewsets.ReadOnlyModelViewSet):
    """Authorized account administrators can view available business roles."""
    queryset = Role.objects.all().order_by('role_id')
    serializer_class = RoleSerializer
    permission_classes = [HRAccountPermission]


class UserAccountViewSet(viewsets.ModelViewSet):
    """HR-managed accounts; DELETE deactivates instead of removing a user."""
    queryset = UserAccount.objects.select_related('employee', 'role').all().order_by('user_id')
    serializer_class = UserAccountSerializer
    permission_classes = [HRAccountPermission]
    http_method_names = ['get', 'post', 'put', 'patch', 'delete', 'head', 'options']

    @transaction.atomic
    def perform_create(self, serializer):
        # Never allow the public account API to create Django superusers/staff.
        account = serializer.save(is_staff=False, is_superuser=False)
        create_audit_log(
            user=self.request.user,
            action='CREATE',
            entity_name='UserAccount',
            entity_id=account.pk,
        )

    @transaction.atomic
    def perform_update(self, serializer):
        account = serializer.instance
        # Avoid self-lockout and changes to privileged Django identities.
        if account.is_superuser or account.is_staff:
            raise PermissionDenied('Privileged Django accounts must be managed through Django admin.')
        if account.pk == self.request.user.pk and serializer.validated_data.get('is_active') is False:
            raise ValidationError({'is_active': 'You cannot deactivate your own account.'})
        account = serializer.save()
        create_audit_log(
            user=self.request.user,
            action='UPDATE',
            entity_name='UserAccount',
            entity_id=account.pk,
        )

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        account = self.get_object()
        if account.pk == request.user.pk:
            raise ValidationError({'error': 'You cannot deactivate your own account.'})
        if account.is_superuser or account.is_staff:
            raise PermissionDenied('Privileged Django accounts must be managed through Django admin.')
        if not account.is_active:
            raise ValidationError({'error': 'This account is already inactive.'})
        account.is_active = False
        account.save(update_fields=['is_active'])
        create_audit_log(
            user=request.user,
            action='UPDATE',
            entity_name='UserAccount',
            entity_id=account.pk,
        )
        return Response({'message': 'User account deactivated successfully.'}, status=status.HTTP_200_OK)
