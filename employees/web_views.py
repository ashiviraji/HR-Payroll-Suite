
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from accounts.models import UserAccount
from audit.utils import create_audit_log

from .forms import EmployeeForm
from .models import Employee


# =========================================================
# PERMISSION HELPERS
# =========================================================

def is_hr_officer(user):
    """
    Check whether the current user is an HR Officer
    or a Django superuser.
    """
    return (
        user.is_superuser
        or (
            user.role_id is not None
            and user.role.role_name == 'HR_OFFICER'
        )
    )


def get_visible_employees(user):
    """
    HR Officers can view all employees.
    Line Managers can view themselves and direct reports.
    Other employees can view their own record.
    """

    queryset = Employee.objects.select_related(
        'department',
        'manager',
    )

    if is_hr_officer(user):
        return queryset

    if user.employee_id is None:
        return queryset.none()

    if (
        user.role_id is not None
        and user.role.role_name == 'LINE_MANAGER'
    ):
        return queryset.filter(
            Q(pk=user.employee_id)
            | Q(manager_id=user.employee_id)
        )

    return queryset.filter(
        pk=user.employee_id
    )


def require_hr_officer(user):
    """
    Restrict employee management operations
    to HR Officers and superusers.
    """
    if not is_hr_officer(user):
        raise PermissionDenied(
            'Only HR Officers can manage employee records.'
        )


# =========================================================
# EMPLOYEE LIST
# =========================================================

@login_required
def employee_list(request):

    employees = get_visible_employees(
        request.user
    ).order_by(
        'first_name',
        'last_name',
    )

    return render(
        request,
        'employees/employee_list.html',
        {
            'employees': employees,
            'can_manage_employees': is_hr_officer(
                request.user
            ),
        }
    )


# =========================================================
# EMPLOYEE DETAILS
# =========================================================

@login_required
def employee_detail(request, pk):

    employee = get_object_or_404(
        get_visible_employees(request.user),
        pk=pk,
    )

    return render(
        request,
        'employees/employee_detail.html',
        {
            'employee': employee,
            'can_manage_employees': is_hr_officer(
                request.user
            ),
        }
    )


# =========================================================
# CREATE EMPLOYEE
# =========================================================

@login_required
@require_http_methods(['GET', 'POST'])
def employee_create(request):

    # Only HR Officers can create employees
    require_hr_officer(request.user)

    if request.method == 'POST':

        form = EmployeeForm(request.POST)

        if form.is_valid():

            with transaction.atomic():

                # Create Employee record
                employee = form.save()

                # Record employee creation in audit logs
                create_audit_log(
                    user=request.user,
                    action='CREATE',
                    entity_name='Employee',
                    entity_id=employee.pk,
                )

            # -----------------------------------------
            # SUCCESS MESSAGE
            # -----------------------------------------

            messages.success(
                request,
                f'Employee {employee.first_name} '
                f'{employee.last_name} '
                f'(ID: {employee.pk}) created successfully.'
            )

            return redirect(
                'employee_detail',
                pk=employee.pk
            )

    else:
        form = EmployeeForm()

    return render(
        request,
        'employees/employee_form.html',
        {
            'form': form,
            'page_title': 'Add Employee',
            'submit_label': 'Create Employee',
            'is_edit': False,
        }
    )


# =========================================================
# UPDATE EMPLOYEE
# =========================================================

@login_required
@require_http_methods(['GET', 'POST'])
def employee_update(request, pk):

    # Only HR Officers can update employee records
    require_hr_officer(request.user)

    employee = get_object_or_404(
        Employee,
        pk=pk,
    )

    if request.method == 'POST':

        form = EmployeeForm(
            request.POST,
            instance=employee,
        )

        if form.is_valid():

            with transaction.atomic():

                # -----------------------------------------
                # UPDATE EMPLOYEE RECORD
                # -----------------------------------------

                employee = form.save()

                # -----------------------------------------
                # SYNCHRONIZE LINKED USER ACCOUNT
                # -----------------------------------------

                linked_account = UserAccount.objects.filter(
                    employee=employee
                ).first()

                if linked_account:

                    # Synchronize employee contact details
                    linked_account.first_name = employee.first_name
                    linked_account.last_name = employee.last_name
                    linked_account.email = employee.email

                    update_fields = [
                        'first_name',
                        'last_name',
                        'email',
                    ]

                    # Deactivate linked account when
                    # employment status is not ACTIVE
                    if employee.employment_status != 'ACTIVE':

                        linked_account.is_active = False

                        update_fields.append(
                            'is_active'
                        )

                    # Save linked user account changes
                    linked_account.save(
                        update_fields=update_fields
                    )

                # -----------------------------------------
                # CREATE AUDIT LOG
                # -----------------------------------------

                create_audit_log(
                    user=request.user,
                    action='UPDATE',
                    entity_name='Employee',
                    entity_id=employee.pk,
                )

            # -----------------------------------------
            # SUCCESS MESSAGE
            # -----------------------------------------

            messages.success(
                request,
                f'Employee {employee.first_name} '
                f'{employee.last_name} '
                f'(ID: {employee.pk}) updated successfully.'
            )

            return redirect(
                'employee_detail',
                pk=employee.pk
            )

    else:
        form = EmployeeForm(
            instance=employee
        )

    return render(
        request,
        'employees/employee_form.html',
        {
            'form': form,
            'employee': employee,
            'page_title': 'Edit Employee',
            'submit_label': 'Save Changes',
            'is_edit': True,
        }
    )


# =========================================================
# DEACTIVATE EMPLOYEE
# =========================================================

@login_required
@require_http_methods(['GET', 'POST'])
def employee_deactivate(request, pk):

    # Only HR Officers can deactivate employees
    require_hr_officer(request.user)

    employee = get_object_or_404(
        Employee,
        pk=pk,
    )

    if request.method == 'POST':

        # Prevent repeated deactivation
        if employee.employment_status != 'ACTIVE':
            return redirect(
                'employee_detail',
                pk=employee.pk
            )

        with transaction.atomic():

            # -----------------------------------------
            # UPDATE EMPLOYMENT STATUS
            # -----------------------------------------

            employee.employment_status = 'INACTIVE'

            employee.save(
                update_fields=['employment_status']
            )

            # -----------------------------------------
            # DEACTIVATE LINKED USER ACCOUNT
            # -----------------------------------------

            UserAccount.objects.filter(
                employee=employee,
                is_active=True,
            ).update(
                is_active=False
            )

            # -----------------------------------------
            # CREATE AUDIT LOG
            # -----------------------------------------

            create_audit_log(
                user=request.user,
                action='UPDATE',
                entity_name='Employee',
                entity_id=employee.pk,
            )

        # -----------------------------------------
        # SUCCESS MESSAGE
        # -----------------------------------------

        messages.success(
            request,
            f'Employee {employee.first_name} '
            f'{employee.last_name} '
            f'(ID: {employee.pk}) deactivated successfully.'
        )

        return redirect(
            'employee_list'
        )

    return render(
        request,
        'employees/employee_confirm_deactivate.html',
        {
            'employee': employee,
        }
    )
