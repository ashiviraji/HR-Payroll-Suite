from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from audit.utils import create_audit_log
from .models import LeaveRequest, LeaveApproval, LeaveAccrual


HOURS_PER_WORKDAY = Decimal('7.60')
BALANCE_REDUCING_STATUSES = ('PENDING', 'MANAGER_APPROVED', 'APPROVED')


# =========================================================
# USER ROLE HELPER
# =========================================================

def get_user_role(user):
    if user.is_superuser:
        return 'SUPERUSER'
    if user.role_id:
        return user.role.role_name
    return None


# =========================================================
# CHECK LEAVE REVIEW PERMISSION
# =========================================================

def can_review_leave(user, leave_request):
    role = get_user_role(user)

    if leave_request.status in ('APPROVED', 'REJECTED'):
        return False

    if role == 'SUPERUSER':
        return True

    if user.employee_id is None:
        return False

    if role == 'LINE_MANAGER':
        return (
            leave_request.status == 'PENDING'
            and leave_request.employee.manager_id == user.employee_id
        )

    if role == 'HR_OFFICER':
        return leave_request.status == 'MANAGER_APPROVED'

    return False


# =========================================================
# LEAVE BALANCE HELPERS
# =========================================================

def get_requested_leave_hours(start_date, end_date):
    """Count weekdays inclusive, using 7.6 hours per weekday.

    This intentionally matches the project's existing leave-day rules.
    It does not exclude public holidays or handle part-time schedules.
    """
    if end_date < start_date:
        raise ValidationError('End date cannot be before start date.')

    weekdays = sum(
        1
        for offset in range((end_date - start_date).days + 1)
        if (start_date + timedelta(days=offset)).weekday() < 5
    )
    return Decimal(weekdays) * HOURS_PER_WORKDAY


def get_available_leave_hours(employee, leave_type, exclude_request_id=None):
    """Return accrued hours less approved leave and active reservations.

    PENDING and MANAGER_APPROVED reserve hours; APPROVED consumes hours.
    REJECTED requests do not reduce the balance. Excluding the current
    request permits validation when editing or finalizing that request.
    """
    accrued_hours = (
        LeaveAccrual.objects.filter(
            employee=employee,
            leave_type=leave_type,
        ).aggregate(total=Sum('hours_accrued'))['total']
        or Decimal('0.00')
    )

    requests = LeaveRequest.objects.filter(
        employee=employee,
        leave_type=leave_type,
        status__in=BALANCE_REDUCING_STATUSES,
    )

    if exclude_request_id is not None:
        requests = requests.exclude(pk=exclude_request_id)

    reserved_or_used_hours = sum(
        (
            get_requested_leave_hours(request.start_date, request.end_date)
            for request in requests
        ),
        Decimal('0.00'),
    )

    return accrued_hours - reserved_or_used_hours


# =========================================================
# VALIDATE LEAVE BALANCE
# =========================================================

def validate_leave_balance(
    employee,
    leave_type,
    start_date,
    end_date,
    exclude_request_id=None,
):
    requested_hours = get_requested_leave_hours(start_date, end_date)

    if not leave_type.is_paid:
        return

    available_hours = get_available_leave_hours(
        employee,
        leave_type,
        exclude_request_id=exclude_request_id,
    )

    if requested_hours > available_hours:
        raise ValidationError(
            'Insufficient leave balance. '
            f'Available: {available_hours} hours. '
            f'Requested: {requested_hours} hours.'
        )


# =========================================================
# APPROVE LEAVE REQUEST
# =========================================================

@transaction.atomic
def approve_leave(user, leave_request_id):
    leave_request = (
        LeaveRequest.objects.select_for_update()
        .select_related('employee', 'leave_type')
        .get(pk=leave_request_id)
    )

    if not can_review_leave(user, leave_request):
        raise PermissionDenied(
            'You do not have permission to approve this leave request.'
        )

    role = get_user_role(user)

    if role == 'SUPERUSER':
        validate_leave_balance(
            leave_request.employee,
            leave_request.leave_type,
            leave_request.start_date,
            leave_request.end_date,
            exclude_request_id=leave_request.pk,
        )
        leave_request.status = 'APPROVED'

    elif role == 'LINE_MANAGER':
        LeaveApproval.objects.create(
            request=leave_request,
            approver=user.employee,
            level=1,
            decision='APPROVED',
            decided_at=timezone.now(),
        )
        leave_request.status = 'MANAGER_APPROVED'

    elif role == 'HR_OFFICER':
        validate_leave_balance(
            leave_request.employee,
            leave_request.leave_type,
            leave_request.start_date,
            leave_request.end_date,
            exclude_request_id=leave_request.pk,
        )
        LeaveApproval.objects.create(
            request=leave_request,
            approver=user.employee,
            level=2,
            decision='APPROVED',
            decided_at=timezone.now(),
        )
        leave_request.status = 'APPROVED'

    else:
        raise PermissionDenied(
            'You do not have permission to approve leave.'
        )

    leave_request.save(update_fields=['status'])

    create_audit_log(
        user=user,
        action='APPROVE',
        entity_name='LeaveRequest',
        entity_id=leave_request.request_id,
    )

    return leave_request


# =========================================================
# REJECT LEAVE REQUEST
# =========================================================

@transaction.atomic
def reject_leave(user, leave_request_id):
    leave_request = (
        LeaveRequest.objects.select_for_update()
        .select_related('employee', 'leave_type')
        .get(pk=leave_request_id)
    )

    if not can_review_leave(user, leave_request):
        raise PermissionDenied(
            'You do not have permission to reject this leave request.'
        )

    role = get_user_role(user)

    if role == 'SUPERUSER':
        leave_request.status = 'REJECTED'

    elif role == 'LINE_MANAGER':
        LeaveApproval.objects.create(
            request=leave_request,
            approver=user.employee,
            level=1,
            decision='REJECTED',
            decided_at=timezone.now(),
        )
        leave_request.status = 'REJECTED'

    elif role == 'HR_OFFICER':
        LeaveApproval.objects.create(
            request=leave_request,
            approver=user.employee,
            level=2,
            decision='REJECTED',
            decided_at=timezone.now(),
        )
        leave_request.status = 'REJECTED'

    else:
        raise PermissionDenied(
            'You do not have permission to reject leave.'
        )

    # Changing the status releases the reservation automatically:
    # get_available_leave_hours() does not count REJECTED requests.
    leave_request.save(update_fields=['status'])

    create_audit_log(
        user=user,
        action='REJECT',
        entity_name='LeaveRequest',
        entity_id=leave_request.request_id,
    )

    return leave_request
