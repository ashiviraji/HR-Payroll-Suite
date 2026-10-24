
from django import forms

from .models import Employee


class EmployeeForm(forms.ModelForm):

    class Meta:
        model = Employee

        fields = [
            'first_name',
            'last_name',
            'email',
            'department',
            'manager',
            'hire_date',
            'employment_status',
        ]

        widgets = {
            'first_name': forms.TextInput(
                attrs={'class': 'form-control'}
            ),
            'last_name': forms.TextInput(
                attrs={'class': 'form-control'}
            ),
            'email': forms.EmailInput(
                attrs={'class': 'form-control'}
            ),
            'department': forms.Select(
                attrs={'class': 'form-select'}
            ),
            'manager': forms.Select(
                attrs={'class': 'form-select'}
            ),
            'hire_date': forms.DateInput(
                attrs={
                    'class': 'form-control',
                    'type': 'date',
                },
                format='%Y-%m-%d',
            ),
            'employment_status': forms.Select(
                attrs={'class': 'form-select'}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['hire_date'].input_formats = [
            '%Y-%m-%d'
        ]

        # Prevent an employee from selecting themselves
        # as their reporting manager.
        if self.instance.pk:
            self.fields['manager'].queryset = (
                Employee.objects.exclude(
                    pk=self.instance.pk
                )
            )
