
from django import forms
from django.core.exceptions import ValidationError

from .models import LeaveRequest


class LeaveRequestForm(forms.ModelForm):

    class Meta:
        model = LeaveRequest

        fields = [
            'leave_type',
            'start_date',
            'end_date',
        ]

        widgets = {
            'leave_type': forms.Select(
                attrs={'class': 'form-select'}
            ),
            'start_date': forms.DateInput(
                attrs={
                    'class': 'form-control',
                    'type': 'date',
                },
                format='%Y-%m-%d',
            ),
            'end_date': forms.DateInput(
                attrs={
                    'class': 'form-control',
                    'type': 'date',
                },
                format='%Y-%m-%d',
            ),
        }

    def clean(self):
        cleaned_data = super().clean()

        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')

        if start_date and end_date and end_date < start_date:
            raise ValidationError(
                'End date cannot be earlier than start date.'
            )

        return cleaned_data
