
from django import forms

from .models import PerformanceReview


class PerformanceReviewForm(forms.ModelForm):

    class Meta:
        model = PerformanceReview

        fields = [
            'cycle',
            'employee',
            'rating',
            'comments',
            'review_date',
        ]

        widgets = {
            'cycle': forms.Select(
                attrs={'class': 'form-select'}
            ),
            'employee': forms.Select(
                attrs={'class': 'form-select'}
            ),
            'rating': forms.NumberInput(
                attrs={
                    'class': 'form-control',
                    'min': 1,
                    'max': 5,
                }
            ),
            'comments': forms.Textarea(
                attrs={
                    'class': 'form-control',
                    'rows': 4,
                    'placeholder': 'Enter performance feedback...',
                }
            ),
            'review_date': forms.DateInput(
                attrs={
                    'class': 'form-control',
                    'type': 'date',
                },
                format='%Y-%m-%d',
            ),
        }
