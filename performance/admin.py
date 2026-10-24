from django.contrib import admin
from .models import ReviewCycle, PerformanceReview


@admin.register(ReviewCycle)
class ReviewCycleAdmin(admin.ModelAdmin):
    list_display = (
        'cycle_id',
        'name',
        'start_date',
        'end_date',
    )


@admin.register(PerformanceReview)
class PerformanceReviewAdmin(admin.ModelAdmin):
    list_display = (
        'review_id',
        'employee',
        'reviewer',
        'cycle',
        'rating',
        'review_date',
    )

    list_filter = (
        'cycle',
        'rating',
    )

    search_fields = (
        'employee__first_name',
        'employee__last_name',
        'reviewer__first_name',
        'reviewer__last_name',
    )