from django.db import models, transaction

from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import BasePermission, IsAuthenticated

from audit.utils import create_audit_log
from .models import ReviewCycle, PerformanceReview
from .serializers import ReviewCycleSerializer, PerformanceReviewSerializer


# =========================================================
# HELPER FUNCTIONS
# =========================================================

def get_user_employee(user):
    try:
        return user.employee
    except (AttributeError, models.ObjectDoesNotExist):
        return None


def get_user_role(user):
    role = getattr(user, 'role', None)
    return getattr(role, 'role_name', None)


def is_hr_or_admin(user):
    return user.is_superuser or get_user_role(user) == 'HR_OFFICER'


class ReviewCyclePermission(BasePermission):
    """All authenticated users may read cycles; only HR/admin may change them."""

    message = 'Only HR Officers or administrators can manage review cycles.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True
        return is_hr_or_admin(request.user)


# =========================================================
# REVIEW CYCLE
# =========================================================

class ReviewCycleViewSet(viewsets.ModelViewSet):
    queryset = ReviewCycle.objects.all()
    serializer_class = ReviewCycleSerializer
    permission_classes = [IsAuthenticated, ReviewCyclePermission]

    @transaction.atomic
    def perform_create(self, serializer):
        cycle = serializer.save()
        create_audit_log(
            user=self.request.user,
            action='CREATE',
            entity_name='ReviewCycle',
            entity_id=cycle.pk,
        )

    @transaction.atomic
    def perform_update(self, serializer):
        cycle = serializer.save()
        create_audit_log(
            user=self.request.user,
            action='UPDATE',
            entity_name='ReviewCycle',
            entity_id=cycle.pk,
        )

    @transaction.atomic
    def perform_destroy(self, instance):
        cycle_id = instance.pk
        instance.delete()
        create_audit_log(
            user=self.request.user,
            action='DELETE',
            entity_name='ReviewCycle',
            entity_id=cycle_id,
        )


# =========================================================
# PERFORMANCE REVIEW
# =========================================================

class PerformanceReviewViewSet(viewsets.ModelViewSet):
    queryset = PerformanceReview.objects.select_related(
        'cycle', 'employee', 'reviewer'
    ).all()
    serializer_class = PerformanceReviewSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = PerformanceReview.objects.select_related(
            'cycle', 'employee', 'reviewer'
        ).all()

        if is_hr_or_admin(user):
            return queryset

        employee = get_user_employee(user)
        if employee is None:
            return queryset.none()

        if get_user_role(user) == 'LINE_MANAGER':
            return queryset.filter(
                models.Q(employee=employee)
                | models.Q(employee__manager=employee)
            )

        return queryset.filter(employee=employee)

    @transaction.atomic
    def perform_create(self, serializer):
        user = self.request.user
        employee = get_user_employee(user)
        role = get_user_role(user)

        if not user.is_superuser and (employee is None or role is None):
            raise PermissionDenied(
                'Your account does not have permission to create performance reviews.'
            )

        target_employee = serializer.validated_data['employee']

        if role == 'LINE_MANAGER' and not user.is_superuser:
            if target_employee.manager_id != employee.pk:
                raise PermissionDenied(
                    'You can only review employees who report directly to you.'
                )
        elif not is_hr_or_admin(user):
            raise PermissionDenied(
                'You do not have permission to create performance reviews.'
            )

        # The current data model identifies the reviewer by an Employee record.
        # Even an administrator must be linked to an employee to create a review.
        if employee is None:
            raise PermissionDenied(
                'A linked employee record is required to identify the reviewer.'
            )

        performance_review = serializer.save(reviewer=employee)
        create_audit_log(
            user=user,
            action='CREATE',
            entity_name='PerformanceReview',
            entity_id=performance_review.review_id,
        )

    @transaction.atomic
    def perform_update(self, serializer):
        user = self.request.user
        if not is_hr_or_admin(user):
            raise PermissionDenied(
                'Only HR Officers or administrators can update performance reviews.'
            )

        instance = serializer.instance
        # Keep review ownership and reviewer identity immutable after creation.
        # Check initial_data as well because a serializer may mark these fields read-only.
        if 'employee' in serializer.initial_data or 'reviewer' in serializer.initial_data:
            raise ValidationError({
                'error': 'Employee and reviewer cannot be changed after creation.'
            })

        performance_review = serializer.save(
            employee=instance.employee,
            reviewer=instance.reviewer,
        )
        create_audit_log(
            user=user,
            action='UPDATE',
            entity_name='PerformanceReview',
            entity_id=performance_review.review_id,
        )

    @transaction.atomic
    def perform_destroy(self, instance):
        user = self.request.user
        if not is_hr_or_admin(user):
            raise PermissionDenied(
                'Only HR Officers or administrators can delete performance reviews.'
            )

        review_id = instance.review_id
        instance.delete()
        create_audit_log(
            user=user,
            action='DELETE',
            entity_name='PerformanceReview',
            entity_id=review_id,
        )
