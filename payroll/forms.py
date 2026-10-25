
from datetime import datetime

from django import forms
from django.db.models import Q

from .models import PayrollRun, SalaryRecord


# =========================================================
# 1. PAYROLL RUN FORM
# =========================================================

class PayrollRunForm(forms.ModelForm):

    class Meta:
        model = PayrollRun

        fields = [
            'period',
            'tax_table',
        ]

        widgets = {
            'period': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'YYYY-MM',
                    'type': 'month',
                }
            ),

            'tax_table': forms.Select(
                attrs={
                    'class': 'form-select',
                }
            ),
        }

        labels = {
            'period': 'Payroll Period',
            'tax_table': 'Tax Table',
        }

    def clean_period(self):

        period = self.cleaned_data['period']

        try:
            datetime.strptime(period, '%Y-%m')

        except ValueError:
            raise forms.ValidationError(
                'Please enter a valid payroll period '
                'in YYYY-MM format.'
            )

        if PayrollRun.objects.filter(
            period=period
        ).exclude(
            pk=self.instance.pk
        ).exists():

            raise forms.ValidationError(
                'A payroll run already exists for this period.'
            )

        return period


# =========================================================
# 2. SALARY RECORD FORM
# =========================================================

class SalaryRecordForm(forms.ModelForm):

    class Meta:
        model = SalaryRecord

        fields = [
            'employee',
            'base_salary',
            'effective_from',
            'effective_to',
        ]

        widgets = {

            'employee': forms.Select(
                attrs={
                    'class': 'form-select',
                }
            ),

            'base_salary': forms.NumberInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Enter base salary',
                    'step': '0.01',
                    'min': '0.01',
                }
            ),

            'effective_from': forms.DateInput(
                attrs={
                    'class': 'form-control',
                    'type': 'date',
                },
                format='%Y-%m-%d'
            ),

            'effective_to': forms.DateInput(
                attrs={
                    'class': 'form-control',
                    'type': 'date',
                },
                format='%Y-%m-%d'
            ),
        }

        labels = {
            'employee': 'Employee',
            'base_salary': 'Base Salary',
            'effective_from': 'Effective From',
            'effective_to': 'Effective To',
        }

    # -----------------------------------------------------
    # INITIALIZE FORM
    # -----------------------------------------------------

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        for field_name in [
            'effective_from',
            'effective_to',
        ]:
            self.fields[field_name].input_formats = [
                '%Y-%m-%d'
            ]

        # Prevent changing the employee when editing
        # an existing salary record.
        if self.instance.pk:
            self.fields['employee'].disabled = True

    # -----------------------------------------------------
    # VALIDATE BASE SALARY
    # -----------------------------------------------------

    def clean_base_salary(self):

        salary = self.cleaned_data.get('base_salary')

        if salary is not None and salary <= 0:
            raise forms.ValidationError(
                'Base salary must be greater than zero.'
            )

        return salary

    # -----------------------------------------------------
    # VALIDATE EFFECTIVE DATES AND OVERLAPPING RECORDS
    # -----------------------------------------------------

    def clean(self):

        cleaned_data = super().clean()

        employee = cleaned_data.get('employee')
        effective_from = cleaned_data.get('effective_from')
        effective_to = cleaned_data.get('effective_to')

        # Validate effective date range.
        if effective_from and effective_to:

            if effective_to < effective_from:

                self.add_error(
                    'effective_to',
                    'Effective To cannot be earlier '
                    'than Effective From.'
                )

                return cleaned_data

        # Check for overlapping salary records.
        if employee and effective_from:

            overlapping_records = (
                SalaryRecord.objects.filter(
                    employee=employee
                )
                .exclude(
                    pk=self.instance.pk
                )
                .filter(
                    Q(effective_to__isnull=True)
                    | Q(effective_to__gte=effective_from)
                )
            )

            # If an end date is provided, only check
            # records starting on or before that date.
            if effective_to is not None:

                overlapping_records = (
                    overlapping_records.filter(
                        effective_from__lte=effective_to
                    )
                )

            if overlapping_records.exists():

                raise forms.ValidationError(
                    'A salary record already exists for '
                    'this employee within the selected '
                    'effective dates.'
                )

        return cleaned_data
