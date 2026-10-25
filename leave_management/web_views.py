from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.views.decorators.http import require_POST

from audit.utils import create_audit_log
from notifications.models import Notification

from .forms import LeaveRequestForm
from .models import LeaveRequest
from .services import (
    approve_leave,
    reject_leave,
    can_review_leave,
    validate_leave_balance,
)


# =========================================================
# ROLE HELPERS
# =========================================================

def get_role_name(user):

    if user.role_id is None:
        return None

    return user.role.role_name


def is_hr_officer(user):

    return (
        user.is_superuser
        or get_role_name(user) == 'HR_OFFICER'
    )


# =========================================================
# VISIBLE LEAVE REQUESTS
# =========================================================

def get_visible_leave_requests(user):

    queryset = LeaveRequest.objects.select_related(
        'employee',
        'leave_type',
    )

    # HR Officer and Superuser can see all requests
    if is_hr_officer(user):
        return queryset

    # Users without linked employees see no requests
    if user.employee_id is None:
        return queryset.none()

    # Line Manager can see own and direct reports' requests
    if get_role_name(user) == 'LINE_MANAGER':

        return queryset.filter(
            Q(employee_id=user.employee_id)
            | Q(employee__manager_id=user.employee_id)
        )

    # Other employees can see only their own requests
    return queryset.filter(
        employee_id=user.employee_id
    )


# =========================================================
# LEAVE REQUEST LIST
# =========================================================

@login_required
def leave_request_list(request):

    leave_requests = list(
        get_visible_leave_requests(request.user)
        .order_by('-start_date', '-request_id')
    )

    # Determine which requests the user can review
    for leave_request in leave_requests:

        leave_request.can_review = can_review_leave(
            request.user,
            leave_request
        )
        leave_request.can_edit_delete = (
            request.user.employee_id is not None
            and leave_request.employee_id == request.user.employee_id
            and leave_request.status == 'PENDING'
        )

    employee = (
        request.user.employee
        if request.user.employee_id is not None
        else None
    )

    can_create_leave = (
        employee is not None
        and employee.employment_status == 'ACTIVE'
    )

    return render(
        request,
        'leave_management/leave_request_list.html',
        {
            'leave_requests': leave_requests,
            'can_create_leave': can_create_leave,
            'can_manage_leaves': is_hr_officer(request.user),
        }
    )


# =========================================================
# CREATE LEAVE REQUEST
# =========================================================

@login_required
def leave_request_create(request):

    employee = (
        request.user.employee
        if request.user.employee_id is not None
        else None
    )

    # Employee account validation
    if employee is None:
        raise PermissionDenied(
            'Your account is not linked to an employee.'
        )

    # Only active employees can request leave
    if employee.employment_status != 'ACTIVE':
        raise PermissionDenied(
            'Inactive employees cannot request leave.'
        )

    if request.method == 'POST':

        form = LeaveRequestForm(request.POST)

        if form.is_valid():

            leave_request = form.save(commit=False)

            # Always use logged-in employee
            leave_request.employee = employee

            # New requests must start as pending
            leave_request.status = 'PENDING'

            # -----------------------------------------
            # VALIDATE LEAVE BALANCE
            # -----------------------------------------

            try:

                validate_leave_balance(
                    employee=employee,
                    leave_type=leave_request.leave_type,
                    start_date=leave_request.start_date,
                    end_date=leave_request.end_date,
                )

            except ValidationError as error:

                form.add_error(
                    None,
                    error
                )

            # -----------------------------------------
            # VALIDATE OVERLAPPING LEAVE
            # -----------------------------------------

            if not form.errors:

                overlapping = LeaveRequest.objects.filter(
                    employee=employee,
                    start_date__lte=leave_request.end_date,
                    end_date__gte=leave_request.start_date,
                ).exclude(
                    status='REJECTED'
                ).exists()

                if overlapping:

                    form.add_error(
                        None,
                        'You already have an overlapping '
                        'leave request.'
                    )

            # -----------------------------------------
            # SAVE LEAVE REQUEST AND NOTIFY MANAGER
            # -----------------------------------------

            if not form.errors:

                with transaction.atomic():
                    # Revalidate immediately before saving the reservation.
                    # The shared service counts pending and approved requests.
                    try:
                        validate_leave_balance(
                            employee=employee,
                            leave_type=leave_request.leave_type,
                            start_date=leave_request.start_date,
                            end_date=leave_request.end_date,
                        )
                    except ValidationError as error:
                        form.add_error(None, error)

                    if form.errors:
                        return render(
                            request,
                            'leave_management/leave_request_form.html',
                            {'form': form},
                        )

                    leave_request.save()

                    create_audit_log(
                        user=request.user,
                        action='CREATE',
                        entity_name='LeaveRequest',
                        entity_id=leave_request.pk,
                    )

                    # Notify only the assigned line manager's
                    # active user account(s).
                    if employee.manager_id is not None:

                        User = get_user_model()

                        manager_users = User.objects.filter(
                            employee_id=employee.manager_id,
                            role__role_name='LINE_MANAGER',
                            is_active=True,
                        )

                        for manager_user in manager_users:

                            Notification.objects.create(
                                recipient=manager_user,
                                notification_type='LEAVE',
                                title='New Leave Request Requires Approval',
                                message=(
                                    f'{employee} has submitted a '
                                    f'leave request from '
                                    f'{leave_request.start_date} to '
                                    f'{leave_request.end_date}. '
                                    f'Please review the request.'
                                ),
                                related_entity='LeaveRequest',
                                related_entity_id=leave_request.request_id,
                            )

                messages.success(
                    request,
                    'Your leave request has been '
                    'submitted successfully.'
                )

                return redirect(
                    'leave_request_list'
                )

    else:

        form = LeaveRequestForm()

    return render(
        request,
        'leave_management/leave_request_form.html',
        {
            'form': form,
        }
    )


# =========================================================
# EDIT OWN PENDING LEAVE REQUEST
# =========================================================

@login_required
def leave_request_edit(request, pk):
    if request.user.employee_id is None:
        raise PermissionDenied('Your account is not linked to an employee.')

    # Ownership enforced at the database query level.
    leave_request = get_object_or_404(
        LeaveRequest,
        pk=pk,
        employee_id=request.user.employee_id,
    )

    if leave_request.status != 'PENDING':
        raise PermissionDenied('Only pending leave requests can be edited.')

    if request.method == 'POST':
        form = LeaveRequestForm(request.POST, instance=leave_request)
        if form.is_valid():
            updated = form.save(commit=False)
            # Never allow a form to change ownership or approval status.
            updated.employee_id = request.user.employee_id
            updated.status = 'PENDING'

            try:
                validate_leave_balance(
                    employee=leave_request.employee,
                    leave_type=updated.leave_type,
                    start_date=updated.start_date,
                    end_date=updated.end_date,
                    exclude_request_id=pk,
                )
            except ValidationError as error:
                form.add_error(None, error)

            if not form.errors:
                overlapping = LeaveRequest.objects.filter(
                    employee_id=request.user.employee_id,
                    start_date__lte=updated.end_date,
                    end_date__gte=updated.start_date,
                ).exclude(pk=pk).exclude(status='REJECTED').exists()
                if overlapping:
                    form.add_error(None, 'You already have an overlapping leave request.')

            if not form.errors:
                with transaction.atomic():
                    # Re-check status while holding a row lock to avoid
                    # editing a request concurrently approved by a manager.
                    locked = LeaveRequest.objects.select_for_update().get(pk=pk)
                    if locked.status != 'PENDING':
                        raise PermissionDenied('This leave request is no longer pending.')
                    try:
                        validate_leave_balance(
                            employee=locked.employee,
                            leave_type=updated.leave_type,
                            start_date=updated.start_date,
                            end_date=updated.end_date,
                            exclude_request_id=pk,
                        )
                    except ValidationError as error:
                        form.add_error(None, error)
                    if form.errors:
                        return render(
                            request,
                            'leave_management/leave_request_form.html',
                            {'form': form, 'is_edit': True, 'leave_request': locked},
                        )
                    locked.leave_type = updated.leave_type
                    locked.start_date = updated.start_date
                    locked.end_date = updated.end_date
                    locked.save(update_fields=['leave_type', 'start_date', 'end_date'])

                    # Keep existing manager notifications in sync with edited dates.
                    Notification.objects.filter(
                        notification_type='LEAVE',
                        related_entity='LeaveRequest',
                        related_entity_id=locked.request_id,
                        title='New Leave Request Requires Approval',
                    ).update(
                        message=(
                            f'{locked.employee} has submitted a '
                            f'leave request from {locked.start_date} to '
                            f'{locked.end_date}. Please review the request.'
                        )
                    )

                    create_audit_log(
                        user=request.user,
                        action='UPDATE',
                        entity_name='LeaveRequest',
                        entity_id=locked.pk,
                    )

                messages.success(request, 'Your leave request has been updated.')
                return redirect('leave_request_list')
    else:
        form = LeaveRequestForm(instance=leave_request)

    return render(request, 'leave_management/leave_request_form.html', {
        'form': form,
        'is_edit': True,
        'leave_request': leave_request,
    })


# =========================================================
# DELETE OWN PENDING LEAVE REQUEST (POST ONLY)
# =========================================================

@login_required
@require_POST
def leave_request_delete(request, pk):
    if request.user.employee_id is None:
        raise PermissionDenied('Your account is not linked to an employee.')

    with transaction.atomic():
        leave_request = get_object_or_404(
            LeaveRequest.objects.select_for_update(),
            pk=pk,
            employee_id=request.user.employee_id,
        )
        if leave_request.status != 'PENDING':
            raise PermissionDenied('Only pending leave requests can be deleted.')

        request_id = leave_request.pk

        # Remove obsolete manager approval notifications for this request.
        Notification.objects.filter(
            notification_type='LEAVE',
            related_entity='LeaveRequest',
            related_entity_id=leave_request.request_id,
            title='New Leave Request Requires Approval',
        ).delete()

        leave_request.delete()
        create_audit_log(
            user=request.user,
            action='DELETE',
            entity_name='LeaveRequest',
            entity_id=request_id,
        )

    messages.success(request, f'Leave request #{request_id} deleted successfully.')
    return redirect('leave_request_list')


# =========================================================
# APPROVE LEAVE REQUEST
# =========================================================

@login_required
@require_POST
def leave_request_approve(request, pk):

    # Ensure request exists and is visible to this user
    get_object_or_404(
        get_visible_leave_requests(request.user),
        pk=pk
    )

    try:

        leave_request = approve_leave(
            user=request.user,
            leave_request_id=pk
        )

        messages.success(
            request,
            f'Leave request #{leave_request.request_id} '
            'approved successfully.'
        )

    except ValidationError as error:

        messages.error(
            request,
            '; '.join(error.messages)
        )

    return redirect(
        'leave_request_list'
    )


# =========================================================
# REJECT LEAVE REQUEST
# =========================================================

@login_required
@require_POST
def leave_request_reject(request, pk):

    # Ensure request exists and is visible to this user
    get_object_or_404(
        get_visible_leave_requests(request.user),
        pk=pk
    )

    try:

        leave_request = reject_leave(
            user=request.user,
            leave_request_id=pk
        )

        messages.success(
            request,
            f'Leave request #{leave_request.request_id} '
            'rejected successfully.'
        )

    except ValidationError as error:

        messages.error(
            request,
            '; '.join(error.messages)
        )

    return redirect(
        'leave_request_list'
    )
