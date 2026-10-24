
from decimal import Decimal
from datetime import datetime
import calendar

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from employees.models import Employee
from accounts.models import UserAccount
from audit.utils import create_audit_log

from .models import (
    PayrollRun,
    SalaryRecord,
    Payslip,
)


# =========================================================
# PAYROLL SERVICE EXCEPTIONS
# =========================================================

class PayrollProcessingError(Exception):
    """Raised when a payroll run cannot be processed."""
    pass


# =========================================================
# PAYROLL PROCESSING SERVICE
# =========================================================

def process_payroll_service(run_id, initiated_by_user_id):
    """
    Execute payroll calculations for a payroll run.

    Intended to be called by a Celery worker after the
    payroll run has been reserved for processing.

    The caller must ensure that the run has been changed
    from PENDING to PROCESSING before invoking this service.
    """

    # -----------------------------------------------------
    # RETRIEVE PAYROLL RUN AND ADMINISTRATOR
    # -----------------------------------------------------

    payroll_run = PayrollRun.objects.select_related(
        'tax_table'
    ).get(pk=run_id)

    initiated_by = UserAccount.objects.get(
        pk=initiated_by_user_id
    )

    if payroll_run.status != 'PROCESSING':
        raise PayrollProcessingError(
            'Payroll run is not in PROCESSING status.'
        )

    # -----------------------------------------------------
    # VALIDATE PAYROLL PERIOD
    # -----------------------------------------------------

    try:
        period_date = datetime.strptime(
            payroll_run.period,
            '%Y-%m'
        )

        year = period_date.year
        month = period_date.month

        period_start = period_date.date()

        last_day = calendar.monthrange(
            year,
            month
        )[1]

        period_end = period_start.replace(
            day=last_day
        )

    except ValueError as exc:
        raise PayrollProcessingError(
            'Payroll period must use YYYY-MM format.'
        ) from exc

    # -----------------------------------------------------
    # VALIDATE TAX TABLE
    # -----------------------------------------------------

    tax_table = payroll_run.tax_table

    if (
        tax_table.effective_from > period_start
        or tax_table.effective_to < period_end
    ):
        raise PayrollProcessingError(
            'The selected tax table does not cover '
            'the payroll period.'
        )

    # -----------------------------------------------------
    # RETRIEVE ACTIVE EMPLOYEES
    # -----------------------------------------------------

    employees = Employee.objects.filter(
        employment_status='ACTIVE'
    )

    created_payslips = []
    skipped_employees = []

    # -----------------------------------------------------
    # PROCESS PAYROLL IN A DATABASE TRANSACTION
    # -----------------------------------------------------

    with transaction.atomic():

        # Recheck status inside the transaction
        payroll_run = PayrollRun.objects.select_for_update().get(
            pk=run_id
        )

        if payroll_run.status != 'PROCESSING':
            raise PayrollProcessingError(
                'Payroll run is no longer available for processing.'
            )

        # Prevent accidental processing of an existing batch
        if Payslip.objects.filter(run=payroll_run).exists():
            raise PayrollProcessingError(
                'Payslips already exist for this payroll run.'
            )

        for employee in employees:

            # ---------------------------------------------
            # FIND APPLICABLE SALARY RECORD
            # ---------------------------------------------

            salary_record = (
                SalaryRecord.objects
                .filter(
                    employee=employee,
                    effective_from__lte=period_end
                )
                .filter(
                    Q(effective_to__isnull=True)
                    | Q(effective_to__gte=period_start)
                )
                .order_by('-effective_from')
                .first()
            )

            if not salary_record:

                skipped_employees.append({
                    'employee_id': employee.pk,
                    'employee_name': str(employee),
                    'reason': (
                        'No applicable salary record '
                        'for this payroll period.'
                    ),
                })

                continue

            # ---------------------------------------------
            # CALCULATE MONTHLY GROSS PAY
            # ---------------------------------------------

            annual_salary = salary_record.base_salary

            gross_pay = (
                annual_salary / Decimal('12')
            ).quantize(
                Decimal('0.01')
            )

            # ---------------------------------------------
            # CALCULATE ANNUAL TAX
            # ---------------------------------------------

            annual_tax = Decimal('0.00')

            brackets = (
                tax_table.tax_brackets
                .all()
                .order_by('lower_bound')
            )

            for bracket in brackets:

                lower = bracket.lower_bound
                upper = bracket.upper_bound

                rate = (
                    bracket.rate / Decimal('100')
                )

                if annual_salary <= lower:
                    continue

                if upper is None:
                    taxable_amount = (
                        annual_salary - lower
                    )
                else:
                    taxable_amount = (
                        min(annual_salary, upper)
                        - lower
                    )

                if taxable_amount > 0:
                    annual_tax += (
                        taxable_amount * rate
                    )

            # ---------------------------------------------
            # CALCULATE MONTHLY TAX
            # ---------------------------------------------

            tax_amount = (
                annual_tax / Decimal('12')
            ).quantize(
                Decimal('0.01')
            )

            total_deductions = tax_amount

            # ---------------------------------------------
            # CALCULATE NET PAY
            # ---------------------------------------------

            net_pay = (
                gross_pay - total_deductions
            ).quantize(
                Decimal('0.01')
            )

            # ---------------------------------------------
            # CREATE EMPLOYEE PAYSLIP
            # ---------------------------------------------

            payslip = Payslip.objects.create(
                run=payroll_run,
                employee=employee,
                gross_pay=gross_pay,
                tax_amount=tax_amount,
                total_deductions=total_deductions,
                net_pay=net_pay,
                pdf_path=''
            )

            created_payslips.append(payslip)

        # ---------------------------------------------
        # PREVENT EMPTY PAYROLL RUNS
        # ---------------------------------------------

        if not created_payslips:
            raise PayrollProcessingError(
                'No eligible employees found for this '
                'payroll period. Please check employee '
                'salary records.'
            )

        # ---------------------------------------------
        # COMPLETE PAYROLL RUN
        # ---------------------------------------------

        payroll_run.status = 'COMPLETED'
        payroll_run.run_at = timezone.now()

        payroll_run.save(
            update_fields=[
                'status',
                'run_at',
            ]
        )

        # ---------------------------------------------
        # CREATE AUDIT LOG
        # ---------------------------------------------

        create_audit_log(
            user=initiated_by,
            action='PROCESS',
            entity_name='PayrollRun',
            entity_id=payroll_run.run_id
        )

    # -----------------------------------------------------
    # RETURN PROCESSING RESULT
    # -----------------------------------------------------

    return {
        'message': 'Payroll processed successfully.',
        'run_id': payroll_run.run_id,
        'period': payroll_run.period,
        'status': payroll_run.status,
        'payslips_created': len(created_payslips),
        'skipped_count': len(skipped_employees),
    }
