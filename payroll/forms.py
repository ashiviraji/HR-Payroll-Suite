
from django import forms

from .models import PayrollRun


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
            from datetime import datetime

            datetime.strptime(period, '%Y-%m')

        except ValueError:
            raise forms.ValidationError(
                'Please enter a valid payroll period in YYYY-MM format.'
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
