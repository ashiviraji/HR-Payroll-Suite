
from rest_framework import serializers

from .models import ReviewCycle, PerformanceReview


# =========================================================
# REVIEW CYCLE SERIALIZER
# =========================================================

class ReviewCycleSerializer(serializers.ModelSerializer):

    class Meta:
        model = ReviewCycle
        fields = [
            'cycle_id',
            'name',
            'start_date',
            'end_date',
        ]

    def validate(self, data):
        start_date = data.get(
            'start_date',
            self.instance.start_date if self.instance else None
        )
        end_date = data.get(
            'end_date',
            self.instance.end_date if self.instance else None
        )

        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError({
                'end_date': 'End date cannot be before start date.'
            })

        return data


# =========================================================
# PERFORMANCE REVIEW SERIALIZER
# =========================================================

class PerformanceReviewSerializer(serializers.ModelSerializer):

    employee_name = serializers.StringRelatedField(
        source='employee',
        read_only=True
    )

    reviewer_name = serializers.StringRelatedField(
        source='reviewer',
        read_only=True
    )

    cycle_name = serializers.CharField(
        source='cycle.name',
        read_only=True
    )

    class Meta:
        model = PerformanceReview
        fields = [
            'review_id',
            'cycle',
            'cycle_name',
            'employee',
            'employee_name',
            'reviewer',
            'reviewer_name',
            'rating',
            'comments',
            'review_date',
        ]

        read_only_fields = [
            'review_id',
            'reviewer',
        ]

    def validate_rating(self, value):
        if not 1 <= value <= 5:
            raise serializers.ValidationError(
                'Rating must be between 1 and 5.'
            )

        return value

    def validate(self, data):

        cycle = data.get(
            'cycle',
            self.instance.cycle if self.instance else None
        )

        review_date = data.get(
            'review_date',
            self.instance.review_date if self.instance else None
        )

        if cycle and review_date:
            if not (
                cycle.start_date <= review_date <= cycle.end_date
            ):
                raise serializers.ValidationError({
                    'review_date':
                        'Review date must fall within the selected review cycle.'
                })

        if self.instance and 'employee' in data:
            if data['employee'].pk != self.instance.employee_id:
                raise serializers.ValidationError({
                    'employee':
                        'The employee assigned to an existing review cannot be changed.'
                })

        return data
