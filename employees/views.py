
from django.db import transaction

from rest_framework import status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from accounts.models import UserAccount
from accounts.permissions import IsHROfficerOrReadOnly
from audit.utils import create_audit_log

from .models import Department, Employee
from .serializers import DepartmentSerializer, EmployeeSerializer


class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    permission_classes = [IsHROfficerOrReadOnly]

    @transaction.atomic
    def perform_create(self, serializer):
        department = serializer.save()

        create_audit_log(
            user=self.request.user,
            action='CREATE',
            entity_name='Department',
            entity_id=department.pk,
        )

    @transaction.atomic
    def perform_update(self, serializer):
        department = serializer.save()

        create_audit_log(
            user=self.request.user,
            action='UPDATE',
            entity_name='Department',
            entity_id=department.pk,
        )

    @transaction.atomic
    def perform_destroy(self, instance):
        department_id = instance.pk
        instance.delete()

        create_audit_log(
            user=self.request.user,
            action='DELETE',
            entity_name='Department',
            entity_id=department_id,
        )


class EmployeeViewSet(viewsets.ModelViewSet):
    queryset = Employee.objects.select_related(
        'department',
        'manager',
    ).all()

    serializer_class = EmployeeSerializer
    permission_classes = [IsHROfficerOrReadOnly]

    # --------------------------------------------------
    # CREATE EMPLOYEE
    # --------------------------------------------------


    @transaction.atomic
    def perform_create(self, serializer):
        employee = serializer.save()

        create_audit_log(
            user=self.request.user,
            action='CREATE',
            entity_name='Employee',
            entity_id=employee.pk,
        )

    # --------------------------------------------------
    # UPDATE EMPLOYEE
    # --------------------------------------------------

    @transaction.atomic
    def perform_update(self, serializer):
        employee = serializer.save()

        # Disable linked account if employee becomes inactive
        if employee.employment_status != 'ACTIVE':
            UserAccount.objects.filter(
                employee=employee,
                is_active=True,
            ).update(is_active=False)

        create_audit_log(
            user=self.request.user,
            action='UPDATE',
            entity_name='Employee',
            entity_id=employee.pk,
        )

    # --------------------------------------------------
    # DEACTIVATE EMPLOYEE
    # --------------------------------------------------

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        employee = self.get_object()

        if employee.employment_status != 'ACTIVE':
            raise ValidationError({
                'employment_status':
                    'This employee is already inactive or terminated.'
            })

        # Soft deactivate employee
        employee.employment_status = 'INACTIVE'
        employee.save(update_fields=['employment_status'])

        # Deactivate linked user account
        UserAccount.objects.filter(
            employee=employee,
            is_active=True,
        ).update(is_active=False)

        create_audit_log(
            user=request.user,
            action='UPDATE',
            entity_name='Employee',
            entity_id=employee.pk,
        )

        return Response(
            {
                'message':
                    'Employee and linked user account deactivated successfully.'
            },
            status=status.HTTP_200_OK,
        )
