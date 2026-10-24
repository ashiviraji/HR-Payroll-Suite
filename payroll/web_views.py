
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Sum
from django.shortcuts import (
    render,
    redirect,
    get_object_or_404,
)
from django.views.decorators.http import require_POST

from audit.utils import create_audit_log

from .models import PayrollRun, Payslip
from .forms import PayrollRunForm
from .tasks import process_payroll_task


logger = logging.getLogger(__name__)


# =========================================================
# 1. ROLE HELPERS
# =========================================================

def get_role_name(user):
    """
    Return the logged-in user's role.
    """

    if user.is_superuser:
        return 'SUPERUSER'

    if user.role_id is None:
        return None

    return user.role.role_name


def is_payroll_admin(user):
    """
    Check whether the user can manage payroll.
    """

    return (
        user.is_superuser
        or get_role_name(user) == 'PAYROLL_ADMIN'
    )


# =========================================================
# 2. PAYROLL RUN LIST
# =========================================================

@login_required
def payroll_run_list(request):
    """
    Display all payroll runs.

    Only Payroll Admins and Superusers
    can access this page.
    """

    if not is_payroll_admin(request.user):
        raise PermissionDenied(
            'You do not have permission '
            'to access payroll management.'
        )

    payroll_runs = (
        PayrollRun.objects
        .select_related('tax_table')
        .prefetch_related('payslips')
        .order_by('-run_id')
    )

    return render(
        request,
        'payroll/payroll_run_list.html',
        {
            'payroll_runs': payroll_runs,
            'can_manage_payroll': True,
        }
    )


# =========================================================
# 3. CREATE PAYROLL RUN
# =========================================================

@login_required
def payroll_run_create(request):
    """
    Create a new payroll run.

    Only Payroll Admins and Superusers
    can create payroll runs.
    """

    if not is_payroll_admin(request.user):
        raise PermissionDenied(
            'You do not have permission '
            'to create payroll runs.'
        )

    if request.method == 'POST':

        form = PayrollRunForm(request.POST)

        if form.is_valid():

            with transaction.atomic():

                payroll_run = form.save()

                create_audit_log(
                    user=request.user,
                    action='CREATE',
                    entity_name='PayrollRun',
                    entity_id=payroll_run.run_id
                )

            messages.success(
                request,
                f'Payroll run #{payroll_run.run_id} '
                'created successfully.'
            )

            return redirect('payroll_run_list')

    else:
        form = PayrollRunForm()

    return render(
        request,
        'payroll/payroll_run_form.html',
        {
            'form': form,
        }
    )


# =========================================================
# 4. PROCESS PAYROLL RUN USING CELERY
# =========================================================

@login_required
@require_POST
def payroll_run_process(request, run_id):
    """
    Queue a pending payroll run for background processing.

    Workflow:
    1. Verify Payroll Admin permissions.
    2. Atomically reserve the pending payroll run.
    3. Change status to PROCESSING.
    4. Submit the job to Celery.
    5. Display a notification.
    """

    # -----------------------------------------------------
    # CHECK PERMISSIONS
    # -----------------------------------------------------

    if not is_payroll_admin(request.user):
        raise PermissionDenied(
            'You do not have permission '
            'to process payroll.'
        )

    # -----------------------------------------------------
    # VERIFY PAYROLL RUN EXISTS
    # -----------------------------------------------------

    payroll_run = get_object_or_404(
        PayrollRun,
        pk=run_id
    )

    # -----------------------------------------------------
    # RESERVE THE PAYROLL RUN
    # -----------------------------------------------------

    # Conditional update prevents two requests from
    # reserving the same pending payroll run.

    reserved = (
        PayrollRun.objects
        .filter(
            pk=payroll_run.pk,
            status='PENDING'
        )
        .update(
            status='PROCESSING'
        )
    )

    if not reserved:

        messages.error(
            request,
            'Only pending payroll runs can be processed.'
        )

        return redirect('payroll_run_list')

    # -----------------------------------------------------
    # SUBMIT BACKGROUND TASK
    # -----------------------------------------------------

    try:

        async_result = process_payroll_task.delay(
            run_id=payroll_run.run_id,
            initiated_by_user_id=request.user.pk
        )

        logger.info(
            'Payroll run #%s queued as Celery task %s',
            payroll_run.run_id,
            async_result.id
        )

    except Exception:

        logger.exception(
            'Failed to queue payroll run #%s',
            payroll_run.run_id
        )

        # Restore the run only if it is still PROCESSING.
        # Do not overwrite a completed run.
        PayrollRun.objects.filter(
            pk=payroll_run.run_id,
            status='PROCESSING'
        ).update(
            status='PENDING'
        )

        messages.error(
            request,
            'Unable to start background payroll '
            'processing. Please check Redis and '
            'the Celery Worker, then try again.'
        )

        return redirect('payroll_run_list')

    # -----------------------------------------------------
    # DISPLAY QUEUE CONFIRMATION
    # -----------------------------------------------------

    messages.success(
        request,
        (
            f'Payroll run #{payroll_run.run_id} '
            'has been submitted for background '
            'processing. Refresh the page to '
            'check its status.'
        )
    )

    return redirect('payroll_run_list')


# =========================================================
# 5. PAYSLIP MANAGEMENT
# =========================================================

@login_required
def payroll_payslip_list(request, run_id):
    """
    Display payslips generated for a payroll run.

    Only Payroll Admins and Superusers
    can view employee payslips.
    """

    # -----------------------------------------------------
    # CHECK PERMISSIONS
    # -----------------------------------------------------

    if not is_payroll_admin(request.user):
        raise PermissionDenied(
            'You do not have permission '
            'to view employee payslips.'
        )

    # -----------------------------------------------------
    # RETRIEVE PAYROLL RUN
    # -----------------------------------------------------

    payroll_run = get_object_or_404(
        PayrollRun.objects.select_related('tax_table'),
        pk=run_id
    )

    # -----------------------------------------------------
    # RETRIEVE PAYSLIPS
    # -----------------------------------------------------

    payslips = (
        Payslip.objects
        .filter(run=payroll_run)
        .select_related('employee', 'run')
        .order_by('employee_id')
    )

    # -----------------------------------------------------
    # CALCULATE PAYROLL TOTALS
    # -----------------------------------------------------

    totals = payslips.aggregate(
        total_gross=Sum('gross_pay'),
        total_tax=Sum('tax_amount'),
        total_deductions=Sum('total_deductions'),
        total_net=Sum('net_pay'),
    )

    # -----------------------------------------------------
    # COUNT GENERATED PAYSLIPS
    # -----------------------------------------------------

    payslip_count = payslips.count()

    # -----------------------------------------------------
    # RENDER PAYSLIP MANAGEMENT PAGE
    # -----------------------------------------------------

    return render(
        request,
        'payroll/payslip_list.html',
        {
            'payroll_run': payroll_run,
            'payslips': payslips,
            'totals': totals,
            'payslip_count': payslip_count,
        }
    )
