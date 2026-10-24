from django.utils import timezone
from django.db import models

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError
from datetime import timedelta
from decimal import Decimal
from django.db.models import Sum
from rest_framework.decorators import api_view, permission_classes
from audit.utils import create_audit_log

from .models import (
    LeaveType,
    LeaveRequest,
    LeaveApproval,
    LeaveAccrual,
)

from .serializers import (
    LeaveTypeSerializer,
    LeaveRequestSerializer,
    LeaveApprovalSerializer,
    LeaveAccrualSerializer,
)


# =========================================================
# LEAVE TYPE
# =========================================================
from rest_framework.permissions import BasePermission


class LeaveTypePermission(BasePermission):
    message = "Only HR Officers can manage leave types."

    def has_permission(self, request, view):
        user = request.user

        if not user or not user.is_authenticated:
            return False

        # All authenticated users can view leave types
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True

        # Superusers can manage leave types
        if user.is_superuser:
            return True

        # Only HR Officers can create, update, or delete
        return bool(
            user.role and
            user.role.role_name == 'HR_OFFICER'
        )


class LeaveTypeViewSet(viewsets.ModelViewSet):
    queryset = LeaveType.objects.all()
    serializer_class = LeaveTypeSerializer
    permission_classes = [IsAuthenticated, LeaveTypePermission]

    def perform_create(self, serializer):
        leave_type = serializer.save()

        create_audit_log(
            user=self.request.user,
            action='CREATE',
            entity_name='LeaveType',
            entity_id=leave_type.leave_type_id
        )

    def perform_update(self, serializer):
        leave_type = serializer.save()

        create_audit_log(
            user=self.request.user,
            action='UPDATE',
            entity_name='LeaveType',
            entity_id=leave_type.leave_type_id
        )

    def perform_destroy(self, instance):
        leave_type_id = instance.leave_type_id
        instance.delete()

        create_audit_log(
            user=self.request.user,
            action='DELETE',
            entity_name='LeaveType',
            entity_id=leave_type_id
        )

# =========================================================
# LEAVE REQUEST
# =========================================================
class LeaveRequestViewSet(viewsets.ModelViewSet):
    queryset = LeaveRequest.objects.select_related(
        'employee',
        'leave_type'
    ).all()

    serializer_class = LeaveRequestSerializer
    permission_classes = [IsAuthenticated]

    # -----------------------------------------------------
    # CONTROL WHICH LEAVE REQUESTS EACH USER CAN SEE
    # -----------------------------------------------------
    def get_queryset(self):
        user = self.request.user

        queryset = LeaveRequest.objects.select_related(
            'employee',
            'leave_type'
        ).all()

        # Superuser can see all leave requests
        if user.is_superuser:
            return queryset

        # User must be linked to an employee
        if not user.employee:
            return queryset.none()

        # User without a role can only see own requests
        if not user.role:
            return queryset.filter(
                employee=user.employee
            )

        role = user.role.role_name

        # HR Officer can see all leave requests
        if role == 'HR_OFFICER':
            return queryset

        # Line Manager can see own requests
        # and requests from direct reports
        if role == 'LINE_MANAGER':
            return queryset.filter(
                models.Q(employee=user.employee)
                | models.Q(employee__manager=user.employee)
            )

        # Employee / Payroll Admin
        # can only see their own requests
        return queryset.filter(
            employee=user.employee
        )

    # Validate available paid leave before creation or final approval.
    def validate_leave_balance(self, employee, leave_type, start_date,
                               end_date, exclude_request_id=None):
        if end_date < start_date:
            raise ValidationError({'error': 'End date cannot be before start date.'})

        if not leave_type.is_paid:
            return

        accrued = LeaveAccrual.objects.filter(
            employee=employee, leave_type=leave_type
        ).aggregate(total=Sum('hours_accrued'))['total'] or Decimal('0.00')

        approved = LeaveRequest.objects.filter(
            employee=employee, leave_type=leave_type, status='APPROVED'
        )
        if exclude_request_id is not None:
            approved = approved.exclude(pk=exclude_request_id)

        def working_days(start, end):
            return sum(1 for n in range((end - start).days + 1)
                       if (start + timedelta(days=n)).weekday() < 5)

        used = sum((Decimal(working_days(item.start_date, item.end_date))
                    * Decimal('7.60') for item in approved), Decimal('0.00'))
        requested = Decimal(working_days(start_date, end_date)) * Decimal('7.60')
        available = accrued - used
        if requested > available:
            raise ValidationError({
                'error': 'Insufficient leave balance.',
                'available_hours': str(available),
                'requested_hours': str(requested),
            })

    def perform_update(self, serializer):
        instance = serializer.instance
        if instance.status != 'PENDING':
            raise ValidationError({'error': 'Only pending leave requests can be edited.'})
        if not self.request.user.is_superuser and (
            not self.request.user.employee or
            instance.employee_id != self.request.user.employee.employee_id
        ):
            raise PermissionDenied('You can only edit your own leave requests.')
        if 'status' in serializer.validated_data or 'employee' in serializer.validated_data:
            raise ValidationError({'error': 'Employee and status cannot be changed here.'})
        leave_type = serializer.validated_data.get('leave_type', instance.leave_type)
        start_date = serializer.validated_data.get('start_date', instance.start_date)
        end_date = serializer.validated_data.get('end_date', instance.end_date)
        self.validate_leave_balance(instance.employee, leave_type, start_date,
                                    end_date, exclude_request_id=instance.pk)
        serializer.save(employee=instance.employee, status=instance.status)

    # -----------------------------------------------------
    # CREATE LEAVE REQUEST
    # -----------------------------------------------------
    def perform_create(self, serializer):
        user = self.request.user
        if not user.employee:
            raise PermissionDenied('Your user account is not linked to an employee.')
        self.validate_leave_balance(
            user.employee,
            serializer.validated_data['leave_type'],
            serializer.validated_data['start_date'],
            serializer.validated_data['end_date'],
        )
        leave_request = serializer.save(employee=user.employee, status='PENDING')
        create_audit_log(user=user, action='CREATE',
                         entity_name='LeaveRequest',
                         entity_id=leave_request.request_id)

    # -----------------------------------------------------
    # DELETE LEAVE REQUEST
    # -----------------------------------------------------
    def perform_destroy(self, instance):
        user = self.request.user

        if instance.status != 'PENDING':
            raise ValidationError({
                'error': 'Only pending leave requests can be deleted.'
            })

        if not user.is_superuser and (
            not user.employee or
            instance.employee_id != user.employee.employee_id
        ):
            raise PermissionDenied(
                'You can only delete your own leave requests.'
            )

        request_id = instance.request_id
        instance.delete()
        create_audit_log(
            user=user,
            action='DELETE',
            entity_name='LeaveRequest',
            entity_id=request_id,
        )

    # -----------------------------------------------------
    # APPROVE LEAVE REQUEST
    # -----------------------------------------------------
    @action(
        detail=True,
        methods=['post'],
        url_path='approve'
    )
    def approve(self, request, pk=None):
        leave_request = self.get_object()
        user = request.user

        if leave_request.status in ('APPROVED', 'REJECTED'):
            raise ValidationError({'error': 'This leave request is already finalized.'})

        # =================================================
        # SUPERUSER APPROVAL
        # =================================================
        if user.is_superuser:
            self.validate_leave_balance(
                leave_request.employee, leave_request.leave_type,
                leave_request.start_date, leave_request.end_date,
                exclude_request_id=leave_request.pk,
            )
            leave_request.status = 'APPROVED'
            leave_request.save(
                update_fields=['status']
            )

            create_audit_log(
                user=user,
                action='APPROVE',
                entity_name='LeaveRequest',
                entity_id=leave_request.request_id
            )

            return Response({
                'message':
                    'Leave request approved by administrator.',
                'status':
                    leave_request.status
            })

        # User must have role and employee
        if not user.role or not user.employee:
            return Response(
                {
                    'error':
                        'User does not have an employee role.'
                },
                status=status.HTTP_403_FORBIDDEN
            )

        role = user.role.role_name

        # =================================================
        # LEVEL 1 - LINE MANAGER APPROVAL
        # =================================================
        if role == 'LINE_MANAGER':

            # Request must still be pending
            if leave_request.status != 'PENDING':
                return Response(
                    {
                        'error':
                            'This request is not awaiting '
                            'manager approval.'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Check that logged-in manager manages employee
            if (
                leave_request.employee.manager_id
                != user.employee.employee_id
            ):
                return Response(
                    {
                        'error':
                            "You are not this employee's "
                            "line manager."
                    },
                    status=status.HTTP_403_FORBIDDEN
                )

            # Create Level 1 approval record
            LeaveApproval.objects.create(
                request=leave_request,
                approver=user.employee,
                level=1,
                decision='APPROVED',
                decided_at=timezone.now()
            )

            # Move request to HR approval
            leave_request.status = 'MANAGER_APPROVED'
            leave_request.save(
                update_fields=['status']
            )

            # Audit log
            create_audit_log(
                user=user,
                action='APPROVE',
                entity_name='LeaveRequest',
                entity_id=leave_request.request_id
            )

            return Response({
                'message':
                    'Leave approved by Line Manager.',
                'status':
                    leave_request.status
            })

        # =================================================
        # LEVEL 2 - HR OFFICER APPROVAL
        # =================================================
        if role == 'HR_OFFICER':

            # Manager must approve first
            if leave_request.status != 'MANAGER_APPROVED':
                return Response(
                    {
                        'error':
                            'The Line Manager must approve '
                            'this request first.'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Create Level 2 approval record
            LeaveApproval.objects.create(
                request=leave_request,
                approver=user.employee,
                level=2,
                decision='APPROVED',
                decided_at=timezone.now()
            )

            self.validate_leave_balance(
                leave_request.employee, leave_request.leave_type,
                leave_request.start_date, leave_request.end_date,
                exclude_request_id=leave_request.pk,
            )

            # Fully approve request
            leave_request.status = 'APPROVED'
            leave_request.save(
                update_fields=['status']
            )

            # Audit log
            create_audit_log(
                user=user,
                action='APPROVE',
                entity_name='LeaveRequest',
                entity_id=leave_request.request_id
            )

            return Response({
                'message':
                    'Leave request fully approved.',
                'status':
                    leave_request.status
            })

        # Other roles cannot approve
        return Response(
            {
                'error':
                    'You do not have permission to approve leave.'
            },
            status=status.HTTP_403_FORBIDDEN
        )

    # -----------------------------------------------------
    # REJECT LEAVE REQUEST
    # -----------------------------------------------------
    @action(
        detail=True,
        methods=['post'],
        url_path='reject'
    )
    def reject(self, request, pk=None):
        leave_request = self.get_object()
        user = request.user

        if leave_request.status in ('APPROVED', 'REJECTED'):
            raise ValidationError({
                'error': 'This leave request is already finalized.'
            })

        # =================================================
        # SUPERUSER REJECTION
        # =================================================
        if user.is_superuser:
            leave_request.status = 'REJECTED'
            leave_request.save(
                update_fields=['status']
            )

            create_audit_log(
                user=user,
                action='REJECT',
                entity_name='LeaveRequest',
                entity_id=leave_request.request_id
            )

            return Response({
                'message':
                    'Leave request rejected by administrator.',
                'status':
                    leave_request.status
            })

        # User must have role and employee
        if not user.role or not user.employee:
            return Response(
                {
                    'error':
                        'User does not have an employee role.'
                },
                status=status.HTTP_403_FORBIDDEN
            )

        role = user.role.role_name

        # =================================================
        # LINE MANAGER REJECTION
        # =================================================
        if role == 'LINE_MANAGER':

            # Manager can reject only pending requests
            if leave_request.status != 'PENDING':
                return Response(
                    {
                        'error':
                            'This request is not awaiting '
                            'manager decision.'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Check manager relationship
            if (
                leave_request.employee.manager_id
                != user.employee.employee_id
            ):
                return Response(
                    {
                        'error':
                            "You are not this employee's "
                            "line manager."
                    },
                    status=status.HTTP_403_FORBIDDEN
                )

            level = 1

        # =================================================
        # HR OFFICER REJECTION
        # =================================================
        elif role == 'HR_OFFICER':

            # HR can reject only after manager approval
            if leave_request.status != 'MANAGER_APPROVED':
                return Response(
                    {
                        'error':
                            'This request is not awaiting '
                            'HR decision.'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            level = 2

        # Other roles cannot reject
        else:
            return Response(
                {
                    'error':
                        'You do not have permission to reject leave.'
                },
                status=status.HTTP_403_FORBIDDEN
            )

        # Record rejection history
        LeaveApproval.objects.create(
            request=leave_request,
            approver=user.employee,
            level=level,
            decision='REJECTED',
            decided_at=timezone.now()
        )

        # Change request status
        leave_request.status = 'REJECTED'
        leave_request.save(
            update_fields=['status']
        )

        # Audit log
        create_audit_log(
            user=user,
            action='REJECT',
            entity_name='LeaveRequest',
            entity_id=leave_request.request_id
        )

        return Response({
            'message':
                'Leave request rejected.',
            'status':
                leave_request.status
        })


# =========================================================
# LEAVE APPROVAL
# =========================================================
class LeaveApprovalViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = LeaveApprovalSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        queryset = LeaveApproval.objects.select_related(
            'request',
            'request__employee',
            'approver'
        )

        if user.is_superuser:
            return queryset

        if not user.employee:
            return queryset.none()

        role = user.role.role_name if user.role else None

        if role == 'HR_OFFICER':
            return queryset

        if role == 'LINE_MANAGER':
            return queryset.filter(
                models.Q(request__employee=user.employee)
                | models.Q(request__employee__manager=user.employee)
            )

        return queryset.filter(
            request__employee=user.employee
        )


# =========================================================
# LEAVE ACCRUAL
# =========================================================
class LeaveAccrualViewSet(viewsets.ModelViewSet):
    serializer_class = LeaveAccrualSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        queryset = LeaveAccrual.objects.select_related(
            'employee',
            'leave_type'
        )

        if user.is_superuser:
            return queryset

        if not user.employee:
            return queryset.none()

        role = user.role.role_name if user.role else None

        if role == 'HR_OFFICER':
            return queryset

        if role == 'LINE_MANAGER':
            return queryset.filter(
                models.Q(employee=user.employee)
                | models.Q(employee__manager=user.employee)
            )

        return queryset.filter(employee=user.employee)

    def check_write_permission(self):
        user = self.request.user

        if user.is_superuser:
            return

        role = user.role.role_name if user.role else None

        if role != 'HR_OFFICER':
            raise PermissionDenied(
                'Only HR Officers can manage leave accruals.'
            )

    def perform_create(self, serializer):
        self.check_write_permission()
        accrual = serializer.save()

        create_audit_log(
            user=self.request.user,
            action='CREATE',
            entity_name='LeaveAccrual',
            entity_id=accrual.accrual_id
        )

    def perform_update(self, serializer):
        self.check_write_permission()
        accrual = serializer.save()

        create_audit_log(
            user=self.request.user,
            action='UPDATE',
            entity_name='LeaveAccrual',
            entity_id=accrual.accrual_id
        )

    def perform_destroy(self, instance):
        self.check_write_permission()

        accrual_id = instance.accrual_id
        instance.delete()

        create_audit_log(
            user=self.request.user,
            action='DELETE',
            entity_name='LeaveAccrual',
            entity_id=accrual_id
        )

# =========================================================
# LEAVE BALANCE
# =========================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def leave_balance(request):

    user = request.user

    employee_id = request.query_params.get('employee_id')
    leave_type_id = request.query_params.get('leave_type_id')

    if not employee_id or not leave_type_id:
        return Response({
            "error": "employee_id and leave_type_id are required."
        }, status=400)

    # Check permissions
    if not user.is_superuser:
        if not user.employee:
            raise PermissionDenied(
                "Your account is not linked to an employee."
            )

        role = user.role.role_name if user.role else None

        if role == 'HR_OFFICER':
            pass
        elif role == 'LINE_MANAGER':
            from employees.models import Employee

            if not Employee.objects.filter(
                employee_id=employee_id
            ).filter(
                models.Q(employee_id=user.employee.employee_id)
                | models.Q(manager=user.employee)
            ).exists():
                raise PermissionDenied(
                    "You cannot view this employee's leave balance."
                )
        elif str(user.employee.employee_id) != str(employee_id):
            raise PermissionDenied(
                "You can only view your own leave balance."
            )

    total_accrued = LeaveAccrual.objects.filter(
        employee_id=employee_id,
        leave_type_id=leave_type_id
    ).aggregate(
        total=Sum('hours_accrued')
    )['total'] or Decimal('0.00')

    approved_requests = LeaveRequest.objects.filter(
        employee_id=employee_id,
        leave_type_id=leave_type_id,
        status='APPROVED'
    )

    total_working_days = 0

    for leave in approved_requests:
        current_date = leave.start_date

        while current_date <= leave.end_date:
            if current_date.weekday() < 5:
                total_working_days += 1

            current_date += timedelta(days=1)

    total_used_hours = (
        Decimal(total_working_days) * Decimal('7.60')
    )

    remaining_balance = total_accrued - total_used_hours

    return Response({
        "employee_id": int(employee_id),
        "leave_type_id": int(leave_type_id),
        "total_accrued_hours": str(total_accrued),
        "total_working_days": total_working_days,
        "total_used_hours": str(total_used_hours),
        "remaining_balance_hours": str(remaining_balance)
    })