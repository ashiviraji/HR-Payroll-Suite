from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from employees.models import Employee


class ReviewCycle(models.Model):
    cycle_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField()

    def clean(self):
        super().clean()
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({
                'end_date': 'End date cannot be earlier than start date.'
            })

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class PerformanceReview(models.Model):
    review_id = models.AutoField(primary_key=True)

    cycle = models.ForeignKey(
        ReviewCycle,
        on_delete=models.PROTECT,
        related_name='performance_reviews'
    )

    employee = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name='performance_reviews'
    )

    reviewer = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name='reviews_given'
    )

    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )

    comments = models.TextField(blank=True)
    review_date = models.DateField()

    def clean(self):
        super().clean()
        if self.cycle_id and self.review_date:
            cycle = self.cycle
            if not cycle.start_date <= self.review_date <= cycle.end_date:
                raise ValidationError({
                    'review_date': 'Review date must fall within the selected review cycle.'
                })

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f'Review #{self.review_id} - {self.employee}'
