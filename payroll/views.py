
from decimal import Decimal
from datetime import datetime
import calendar

from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from employees.models import Employee
from accounts.permissions import IsPayrollAdmin
from audit.utils import create_audit_log

from .pdf_utils import generate_payslip_pdf

from .models import (
    SalaryRecord,
    TaxTable,
    TaxBracket,
    PayrollRun,
    Payslip,
)

from .serializers import (
    SalaryRecordSerializer,
    TaxTableSerializer,
    TaxBracketSerializer,
    PayrollRunSerializer,
    PayslipSerializer,
)


# =========================================================
# 1. SALARY RECORD MANAGEMENT
# =========================================================

class SalaryRecordViewSet(viewsets.ModelViewSet):

    queryset = SalaryRecord.objects.select_related(
        'employee'
    ).all()

    serializer_class = SalaryRecordSerializer
    permission_classes = [IsPayrollAdmin]


# =========================================================
# 2. TAX TABLE MANAGEMENT
# =========================================================

class TaxTableViewSet(viewsets.ModelViewSet):

    queryset = TaxTable.objects.prefetch_related(
        'tax_brackets'
    ).all()

    serializer_class = TaxTableSerializer
    permission_classes = [IsPayrollAdmin]


# =========================================================
# 3. TAX BRACKET MANAGEMENT
# =========================================================

class TaxBracketViewSet(viewsets.ModelViewSet):

    queryset = TaxBracket.objects.select_related(
        'tax_table'
    ).all()

    serializer_class = TaxBracketSerializer
    permission_classes = [IsPayrollAdmin]


# =========================================================
# 4. PAYROLL PROCESSING
# =========================================================

class PayrollRunViewSet(viewsets.ModelViewSet):

    queryset = PayrollRun.objects.select_related(
        'tax_table'
    ).all()

    serializer_class = PayrollRunSerializer
    permission_classes = [IsPayrollAdmin]

    @action(
        detail=True,
        methods=['post'],
        url_path='process'
    )
    def process_payroll(self, request, pk=None):

        payroll_run = self.get_object()

        # Prevent processing runs that are not pending
        if payroll_run.status != 'PENDING':
            return Response(
                {
                    'detail': (
                        'Only pending payroll runs can be processed.'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # -------------------------------------------------
        # VALIDATE PAYROLL PERIOD
        # -------------------------------------------------

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

        except ValueError:
            return Response(
                {
                    'detail': (
                        'Payroll period must use YYYY-MM format.'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # -------------------------------------------------
        # VALIDATE TAX TABLE
        # -------------------------------------------------

        if (
            payroll_run.tax_table.effective_from > period_start
            or payroll_run.tax_table.effective_to < period_end
        ):
            return Response(
                {
                    'detail': (
                        'The selected tax table does not '
                        'cover the payroll period.'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # -------------------------------------------------
        # GET ACTIVE EMPLOYEES
        # -------------------------------------------------

        employees = Employee.objects.filter(
            employment_status='ACTIVE'
        )

        created_payslips = []
        skipped_employees = []

        # -------------------------------------------------
        # PROCESS PAYROLL
        # -------------------------------------------------

        with transaction.atomic():

            payroll_run.status = 'PROCESSING'
            payroll_run.save(
                update_fields=['status']
            )

            for employee in employees:

                # Find applicable salary record
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

                # Skip employees without salary records
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

                # -----------------------------------------
                # CALCULATE GROSS PAY
                # -----------------------------------------

                annual_salary = salary_record.base_salary

                gross_pay = (
                    annual_salary / Decimal('12')
                ).quantize(
                    Decimal('0.01')
                )

                # -----------------------------------------
                # CALCULATE ANNUAL TAX
                # -----------------------------------------

                annual_tax = Decimal('0.00')

                brackets = (
                    payroll_run.tax_table
                    .tax_brackets
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

                # -----------------------------------------
                # CALCULATE MONTHLY TAX
                # -----------------------------------------

                tax_amount = (
                    annual_tax / Decimal('12')
                ).quantize(
                    Decimal('0.01')
                )

                total_deductions = tax_amount

                # -----------------------------------------
                # CALCULATE NET PAY
                # -----------------------------------------

                net_pay = (
                    gross_pay - total_deductions
                ).quantize(
                    Decimal('0.01')
                )

                # -----------------------------------------
                # CREATE PAYSLIP
                # -----------------------------------------

                payslip, created = (
                    Payslip.objects.update_or_create(
                        run=payroll_run,
                        employee=employee,
                        defaults={
                            'gross_pay': gross_pay,
                            'tax_amount': tax_amount,
                            'total_deductions':
                                total_deductions,
                            'net_pay': net_pay,
                            'pdf_path': '',
                        }
                    )
                )

                created_payslips.append(payslip)

            # Do not complete a payroll run with zero payslips.
            if not created_payslips:
                payroll_run.status = 'PENDING'
                payroll_run.save(update_fields=['status'])
                return Response(
                    {
                        'detail': (
                            'No eligible employees found for this '
                            'payroll period. Please check employee '
                            'salary records.'
                        ),
                        'skipped_count': len(skipped_employees),
                    },
                    status=status.HTTP_400_BAD_REQUEST
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
            # AUDIT LOG
            # ---------------------------------------------

            create_audit_log(
                user=request.user,
                action='PROCESS',
                entity_name='PayrollRun',
                entity_id=payroll_run.run_id
            )

        # -------------------------------------------------
        # RETURN PROCESSING RESULT
        # -------------------------------------------------

        return Response(
            {
                'message': (
                    'Payroll processed successfully.'
                ),
                'run_id': payroll_run.run_id,
                'period': payroll_run.period,
                'status': payroll_run.status,
                'payslips_created': len(created_payslips),
                'skipped_count': len(skipped_employees),
                'skipped_employees': skipped_employees,
                'warnings': [
                    (
                        f"{employee['employee_name']}: "
                        f"{employee['reason']}"
                    )
                    for employee in skipped_employees
                ],
            },
            status=status.HTTP_200_OK
        )


# =========================================================
# 5. PAYSLIP MANAGEMENT AND PDF DOWNLOAD
# =========================================================

class PayslipViewSet(viewsets.ReadOnlyModelViewSet):

    serializer_class = PayslipSerializer
    permission_classes = [IsAuthenticated]

    # -----------------------------------------------------
    # ROLE-BASED PAYSLIP ACCESS
    # -----------------------------------------------------

    def get_queryset(self):

        user = self.request.user

        queryset = Payslip.objects.select_related(
            'run',
            'employee'
        ).all()

        # Superuser can view all payslips
        if user.is_superuser:
            return queryset

        # Payroll Admin can view all payslips
        if (
            user.role
            and user.role.role_name == 'PAYROLL_ADMIN'
        ):
            return queryset

        # Other users must have an employee account
        employee = getattr(
            user,
            'employee',
            None
        )

        if employee is None:
            return queryset.none()

        # Employees can view only their own payslips
        return queryset.filter(
            employee=employee
        )

    # -----------------------------------------------------
    # DOWNLOAD PAYSLIP PDF
    # -----------------------------------------------------

    @action(
        detail=True,
        methods=['get'],
        url_path='download'
    )
    def download_payslip(self, request, pk=None):

        # Get payslip with permission filtering
        payslip = self.get_object()

        # Generate payslip PDF
        pdf_content = generate_payslip_pdf(
            payslip
        )

        response = HttpResponse(
            pdf_content,
            content_type='application/pdf'
        )

        filename = (
            f"payslip_{payslip.payslip_id}_"
            f"{payslip.run.period}.pdf"
        )

        response['Content-Disposition'] = (
            f'attachment; filename="{filename}"'
        )

        # Prevent caching of sensitive payroll PDFs
        response['Cache-Control'] = 'no-store'

        return response
