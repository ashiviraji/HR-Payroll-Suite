
from datetime import datetime

from rest_framework import serializers

from .models import (
    SalaryRecord,
    TaxTable,
    TaxBracket,
    PayrollRun,
    Payslip,
)


# ============================================================
# 1. SALARY RECORD SERIALIZER
# ============================================================

class SalaryRecordSerializer(serializers.ModelSerializer):

    employee_name = serializers.CharField(
        source='employee.__str__',
        read_only=True
    )

    class Meta:
        model = SalaryRecord
        fields = [
            'salary_id',
            'employee',
            'employee_name',
            'base_salary',
            'effective_from',
            'effective_to',
        ]

    def validate_base_salary(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "Base salary must be greater than zero."
            )
        return value

    def validate(self, data):

        employee = data.get(
            'employee',
            self.instance.employee if self.instance else None
        )

        effective_from = data.get(
            'effective_from',
            self.instance.effective_from if self.instance else None
        )

        effective_to = data.get(
            'effective_to',
            self.instance.effective_to if self.instance else None
        )

        # Validate salary effective dates
        if (
            effective_from is not None
            and effective_to is not None
            and effective_to < effective_from
        ):
            raise serializers.ValidationError({
                "effective_to": (
                    "Effective-to date cannot be before effective-from date."
                )
            })

        # Prevent overlapping salary records for the same employee
        if employee is not None and effective_from is not None:

            existing_records = SalaryRecord.objects.filter(
                employee=employee
            )

            # Exclude current record when updating
            if self.instance:
                existing_records = existing_records.exclude(
                    pk=self.instance.pk
                )

            for record in existing_records:

                overlaps = (
                    (
                        record.effective_to is None
                        or effective_from <= record.effective_to
                    )
                    and
                    (
                        effective_to is None
                        or record.effective_from <= effective_to
                    )
                )

                if overlaps:
                    raise serializers.ValidationError({
                        "effective_from": (
                            "Salary record dates overlap with "
                            "an existing salary record."
                        )
                    })

        return data


# ============================================================
# 2. TAX BRACKET SERIALIZER
# ============================================================

class TaxBracketSerializer(serializers.ModelSerializer):

    class Meta:
        model = TaxBracket
        fields = [
            'bracket_id',
            'tax_table',
            'lower_bound',
            'upper_bound',
            'rate',
        ]

    def validate_rate(self, value):
        if value < 0 or value > 100:
            raise serializers.ValidationError(
                "Tax rate must be between 0 and 100."
            )
        return value

    def validate_lower_bound(self, value):
        if value < 0:
            raise serializers.ValidationError(
                "Lower bound cannot be negative."
            )
        return value

    def validate(self, data):

        lower_bound = data.get(
            'lower_bound',
            self.instance.lower_bound if self.instance else None
        )

        upper_bound = data.get(
            'upper_bound',
            self.instance.upper_bound if self.instance else None
        )

        tax_table = data.get(
            'tax_table',
            self.instance.tax_table if self.instance else None
        )

        # Validate upper and lower bounds
        if (
            lower_bound is not None
            and upper_bound is not None
            and upper_bound <= lower_bound
        ):
            raise serializers.ValidationError(
                "Upper bound must be greater than lower bound."
            )

        # Prevent overlapping tax brackets
        if tax_table is not None and lower_bound is not None:

            existing_brackets = TaxBracket.objects.filter(
                tax_table=tax_table
            )

            # Exclude current bracket when updating
            if self.instance:
                existing_brackets = existing_brackets.exclude(
                    pk=self.instance.pk
                )

            for bracket in existing_brackets:

                existing_lower = bracket.lower_bound
                existing_upper = bracket.upper_bound

                overlaps = (
                    (
                        existing_upper is None
                        or lower_bound < existing_upper
                    )
                    and
                    (
                        upper_bound is None
                        or existing_lower < upper_bound
                    )
                )

                if overlaps:
                    raise serializers.ValidationError(
                        "Tax bracket overlaps with an existing bracket."
                    )

        return data


# ============================================================
# 3. TAX TABLE SERIALIZER
# ============================================================

class TaxTableSerializer(serializers.ModelSerializer):

    tax_brackets = TaxBracketSerializer(
        many=True,
        read_only=True
    )

    class Meta:
        model = TaxTable
        fields = [
            'tax_table_id',
            'financial_year',
            'effective_from',
            'effective_to',
            'tax_brackets',
        ]

    def validate(self, data):

        effective_from = data.get(
            'effective_from',
            self.instance.effective_from if self.instance else None
        )

        effective_to = data.get(
            'effective_to',
            self.instance.effective_to if self.instance else None
        )

        if (
            effective_from is not None
            and effective_to is not None
            and effective_to < effective_from
        ):
            raise serializers.ValidationError(
                "Effective-to date cannot be before effective-from date."
            )

        return data


# ============================================================
# 4. PAYROLL RUN SERIALIZER
# ============================================================

class PayrollRunSerializer(serializers.ModelSerializer):

    financial_year = serializers.CharField(
        source='tax_table.financial_year',
        read_only=True
    )

    class Meta:
        model = PayrollRun
        fields = [
            'run_id',
            'tax_table',
            'financial_year',
            'period',
            'status',
            'run_at',
        ]

        read_only_fields = [
            'status',
            'run_at',
        ]

    def validate_period(self, value):

        try:
            parsed = datetime.strptime(value, "%Y-%m")

            if parsed.strftime("%Y-%m") != value:
                raise ValueError

        except ValueError:
            raise serializers.ValidationError(
                "Payroll period must be in YYYY-MM format."
            )

        return value

    def validate(self, data):

        period = data.get(
            'period',
            self.instance.period if self.instance else None
        )

        # Prevent duplicate payroll periods
        if period is not None:

            existing_runs = PayrollRun.objects.filter(
                period=period
            )

            # Exclude current run when updating
            if self.instance:
                existing_runs = existing_runs.exclude(
                    pk=self.instance.pk
                )

            if existing_runs.exists():
                raise serializers.ValidationError({
                    "period": (
                        "A payroll run already exists for this period."
                    )
                })

        return data


# ============================================================
# 5. PAYSLIP SERIALIZER
# ============================================================

class PayslipSerializer(serializers.ModelSerializer):

    employee_name = serializers.CharField(
        source='employee.__str__',
        read_only=True
    )

    payroll_period = serializers.CharField(
        source='run.period',
        read_only=True
    )

    class Meta:
        model = Payslip
        fields = [
            'payslip_id',
            'run',
            'payroll_period',
            'employee',
            'employee_name',
            'gross_pay',
            'tax_amount',
            'total_deductions',
            'net_pay',
            'pdf_path',
        ]

        read_only_fields = [
            'gross_pay',
            'tax_amount',
            'total_deductions',
            'net_pay',
            'pdf_path',
        ]
