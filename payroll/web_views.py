
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

from .models import (
    PayrollRun,
    Payslip,
    SalaryRecord,
)

from .forms import (
    PayrollRunForm,
    SalaryRecordForm,
)

from .tasks import process_payroll_task


logger = logging.getLogger(__name__)


# =========================================================
# 1. ROLE HELPERS
# =========================================================

def get_role_name(user):

    if user.is_superuser:
        return 'SUPERUSER'

    role = getattr(user, 'role', None)

    if role:
        return role.role_name

    return None


def is_payroll_admin(user):

    if user.is_superuser:
        return True

    return get_role_name(user) == 'PAYROLL_ADMIN'


# =========================================================
# 2. VIEW PAYROLL RUNS
# =========================================================

@login_required
def payroll_run_list(request):

    if not is_payroll_admin(request.user):
        raise PermissionDenied(
            'Only Payroll Administrators can view payroll runs.'
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
        }
    )


# =========================================================
# 3. CREATE PAYROLL RUN
# =========================================================

@login_required
def payroll_run_create(request):

    if not is_payroll_admin(request.user):
        raise PermissionDenied(
            'Only Payroll Administrators can create payroll runs.'
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
                'Payroll run created successfully.'
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

    if not is_payroll_admin(request.user):
        raise PermissionDenied(
            'Only Payroll Administrators can process payroll.'
        )

    with transaction.atomic():

        updated = PayrollRun.objects.filter(
            pk=run_id,
            status='PENDING'
        ).update(
            status='PROCESSING'
        )

    if not updated:

        payroll_run = get_object_or_404(
            PayrollRun,
            pk=run_id
        )

        messages.warning(
            request,
            'This payroll run cannot be processed '
            f'because its status is {payroll_run.status}.'
        )

        return redirect('payroll_run_list')

    try:

        process_payroll_task.delay(
            run_id,
            request.user.pk
        )

        messages.success(
            request,
            'Payroll processing has been queued successfully.'
        )

    except Exception:

        logger.exception(
            'Failed to queue payroll run %s',
            run_id
        )

        PayrollRun.objects.filter(
            pk=run_id,
            status='PROCESSING'
        ).update(
            status='PENDING'
        )

        messages.error(
            request,
            'Unable to queue payroll processing. '
            'Please check the Celery worker and Redis connection.'
        )

    return redirect('payroll_run_list')


# =========================================================
# 5. VIEW PAYSLIPS FOR A PAYROLL RUN
# =========================================================

@login_required
def payroll_payslip_list(request, run_id):

    if not is_payroll_admin(request.user):
        raise PermissionDenied(
            'Only Payroll Administrators can view payroll payslips.'
        )

    payroll_run = get_object_or_404(
        PayrollRun.objects.select_related('tax_table'),
        pk=run_id
    )

    payslips = (
        Payslip.objects
        .filter(run=payroll_run)
        .select_related('employee')
        .order_by('employee_id')
    )

    totals = payslips.aggregate(
        total_gross=Sum('gross_pay'),
        total_tax=Sum('tax_amount'),
        total_deductions=Sum('total_deductions'),
        total_net=Sum('net_pay')
    )

    return render(
        request,
        'payroll/payslip_list.html',
        {
            'payroll_run': payroll_run,
            'payslips': payslips,
            'totals': totals,
        }
    )


# =========================================================
# 6. VIEW EMPLOYEE SALARY RECORDS
# =========================================================

@login_required
def salary_record_list(request):

    if not is_payroll_admin(request.user):
        raise PermissionDenied(
            'Only Payroll Administrators can view salary records.'
        )

    salary_records = (
        SalaryRecord.objects
        .select_related('employee')
        .order_by(
            'employee_id',
            '-effective_from'
        )
    )

    return render(
        request,
        'payroll/salary_record_list.html',
        {
            'salary_records': salary_records,
        }
    )


# =========================================================
# 7. CREATE EMPLOYEE SALARY RECORD
# =========================================================

@login_required
def salary_record_create(request):

    if not is_payroll_admin(request.user):
        raise PermissionDenied(
            'Only Payroll Administrators can create salary records.'
        )

    if request.method == 'POST':

        form = SalaryRecordForm(request.POST)

        if form.is_valid():

            with transaction.atomic():

                salary_record = form.save()

                create_audit_log(
                    user=request.user,
                    action='CREATE',
                    entity_name='SalaryRecord',
                    entity_id=salary_record.salary_id
                )

            messages.success(
                request,
                'Employee salary record created successfully.'
            )

            return redirect('salary_record_list')

    else:

        form = SalaryRecordForm()

    return render(
        request,
        'payroll/salary_record_form.html',
        {
            'form': form,
            'page_title': 'Add Employee Salary',
        }
    )


# =========================================================
# 8. UPDATE EMPLOYEE SALARY RECORD
# =========================================================

@login_required
def salary_record_update(request, salary_id):

    if not is_payroll_admin(request.user):
        raise PermissionDenied(
            'Only Payroll Administrators can update salary records.'
        )

    salary_record = get_object_or_404(
        SalaryRecord,
        pk=salary_id
    )

    if request.method == 'POST':

        form = SalaryRecordForm(
            request.POST,
            instance=salary_record
        )

        if form.is_valid():

            with transaction.atomic():

                updated_record = form.save()

                create_audit_log(
                    user=request.user,
                    action='UPDATE',
                    entity_name='SalaryRecord',
                    entity_id=updated_record.salary_id
                )

            messages.success(
                request,
                'Employee salary record updated successfully.'
            )

            return redirect('salary_record_list')

    else:

        form = SalaryRecordForm(
            instance=salary_record
        )

    return render(
        request,
        'payroll/salary_record_form.html',
        {
            'form': form,
            'page_title': 'Update Employee Salary',
        }
    )
