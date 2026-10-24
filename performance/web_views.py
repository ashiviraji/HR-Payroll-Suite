
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.shortcuts import redirect, render

from audit.utils import create_audit_log
from employees.models import Employee

from .forms import PerformanceReviewForm
from .models import PerformanceReview


# =========================================================
# ROLE HELPERS
# =========================================================

def get_role_name(user):

    if user.is_superuser:
        return 'SUPERUSER'

    if user.role_id is None:
        return None

    return user.role.role_name


def is_hr_officer(user):

    return (
        user.is_superuser
        or get_role_name(user) == 'HR_OFFICER'
    )


# =========================================================
# CHECK PERFORMANCE REVIEW CREATION PERMISSION
# =========================================================

def can_create_performance_review(user):

    role = get_role_name(user)

    # Only HR Officers, Superusers and Line Managers
    # can create performance reviews.
    if not (
        is_hr_officer(user)
        or role == 'LINE_MANAGER'
    ):
        return False

    # The account must be linked to an employee.
    if user.employee_id is None:
        return False

    # Only active employees can create reviews.
    if user.employee.employment_status != 'ACTIVE':
        return False

    return True


# =========================================================
# VISIBLE PERFORMANCE REVIEWS
# =========================================================

def get_visible_performance_reviews(user):

    queryset = PerformanceReview.objects.select_related(
        'cycle',
        'employee',
        'reviewer'
    )

    # HR Officers and Superusers can view all reviews.
    if is_hr_officer(user):
        return queryset

    # Users without a linked employee cannot view reviews.
    if user.employee_id is None:
        return queryset.none()

    # Line Managers can view their own reviews
    # and reviews of their direct reports.
    if get_role_name(user) == 'LINE_MANAGER':

        return queryset.filter(
            Q(employee_id=user.employee_id)
            | Q(employee__manager_id=user.employee_id)
        ).distinct()

    # Regular employees and Payroll Admins
    # can view only their own reviews.
    return queryset.filter(
        employee_id=user.employee_id
    )


# =========================================================
# PERFORMANCE REVIEW LIST
# =========================================================

@login_required
def performance_review_list(request):

    reviews = (
        get_visible_performance_reviews(request.user)
        .order_by('-review_date', '-review_id')
    )

    return render(
        request,
        'performance/performance_review_list.html',
        {
            'reviews': reviews,

            'can_manage_reviews': is_hr_officer(
                request.user
            ),

            'can_create_review': can_create_performance_review(
                request.user
            ),
        }
    )


# =========================================================
# CREATE PERFORMANCE REVIEW
# =========================================================

@login_required
def performance_review_create(request):

    user = request.user

    # -----------------------------------------------------
    # STEP 1: CHECK USER PERMISSIONS
    # -----------------------------------------------------

    if not can_create_performance_review(user):

        raise PermissionDenied(
            'You do not have permission to create '
            'performance reviews.'
        )

    # Automatically assign the logged-in employee
    # as the reviewer.
    reviewer = user.employee

    # -----------------------------------------------------
    # STEP 2: GET AUTHORIZED EMPLOYEES
    # -----------------------------------------------------

    if is_hr_officer(user):

        # HR Officers and Superusers can review
        # all active employees.
        allowed_employees = Employee.objects.filter(
            employment_status='ACTIVE'
        )

    else:

        # Line Managers can review only their
        # active direct reports.
        allowed_employees = Employee.objects.filter(
            manager_id=reviewer.pk,
            employment_status='ACTIVE'
        )

    # -----------------------------------------------------
    # STEP 3: INITIALIZE PERFORMANCE REVIEW FORM
    # -----------------------------------------------------

    if request.method == 'POST':
        form = PerformanceReviewForm(request.POST)
    else:
        form = PerformanceReviewForm()

    # Restrict the employee dropdown based on permissions.
    # This also validates submitted employee IDs.
    form.fields['employee'].queryset = allowed_employees

    # -----------------------------------------------------
    # STEP 4: VALIDATE AND SAVE PERFORMANCE REVIEW
    # -----------------------------------------------------

    if request.method == 'POST' and form.is_valid():

        performance_review = form.save(commit=False)

        # The reviewer cannot be selected manually.
        # Always use the logged-in employee.
        performance_review.reviewer = reviewer

        with transaction.atomic():

            # Save the performance review.
            performance_review.save()

            # Record the creation in the audit log.
            create_audit_log(
                user=user,
                action='CREATE',
                entity_name='PerformanceReview',
                entity_id=performance_review.pk,
            )

        # Display success message.
        messages.success(
            request,
            f'Performance review #{performance_review.pk} '
            'created successfully.'
        )

        # Redirect to performance review list.
        return redirect('performance_review_list')

    # -----------------------------------------------------
    # STEP 5: DISPLAY PERFORMANCE REVIEW FORM
    # -----------------------------------------------------

    return render(
        request,
        'performance/performance_review_form.html',
        {
            'form': form,
        }
    )
