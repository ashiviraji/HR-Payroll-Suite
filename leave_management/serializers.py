from rest_framework import serializers

from .models import (
    LeaveType,
    LeaveRequest,
    LeaveApproval,
    LeaveAccrual,
)


# =========================================================
# LEAVE TYPE SERIALIZER
# =========================================================
class LeaveTypeSerializer(serializers.ModelSerializer):

    class Meta:
        model = LeaveType
        fields = [
            'leave_type_id',
            'name',
            'accrual_rate',
            'is_paid',
        ]


# =========================================================
# LEAVE REQUEST SERIALIZER
# =========================================================
class LeaveRequestSerializer(serializers.ModelSerializer):

    employee_name = serializers.CharField(
        source='employee.__str__',
        read_only=True
    )

    leave_type_name = serializers.CharField(
        source='leave_type.name',
        read_only=True
    )

    class Meta:
        model = LeaveRequest

        fields = [
            'request_id',
            'employee',
            'employee_name',
            'leave_type',
            'leave_type_name',
            'start_date',
            'end_date',
            'status',
        ]

        read_only_fields = [
            'employee',
            'status',
        ]

    def validate(self, data):

        # Get dates for create or update
        start_date = data.get(
            'start_date',
            self.instance.start_date if self.instance else None
        )

        end_date = data.get(
            'end_date',
            self.instance.end_date if self.instance else None
        )

        # Validate date range
        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError({
                'end_date': 'End date cannot be before start date.'
            })

        # Identify the employee
        request = self.context.get('request')

        if self.instance:
            employee = self.instance.employee
        else:
            employee = (
                getattr(request.user, 'employee', None)
                if request else None
            )

        # Prevent overlapping leave requests
        if employee and start_date and end_date:

            overlapping_requests = LeaveRequest.objects.filter(
                employee=employee,
                status__in=[
                    'PENDING',
                    'MANAGER_APPROVED',
                    'APPROVED',
                ],
                start_date__lte=end_date,
                end_date__gte=start_date
            )

            # Exclude the current request during updates
            if self.instance:
                overlapping_requests = overlapping_requests.exclude(
                    pk=self.instance.pk
                )

            if overlapping_requests.exists():
                raise serializers.ValidationError({
                    'error': (
                        'You already have an active leave request '
                        'that overlaps with these dates.'
                    )
                })

        return data


# =========================================================
# LEAVE APPROVAL SERIALIZER
# =========================================================
class LeaveApprovalSerializer(serializers.ModelSerializer):

    class Meta:
        model = LeaveApproval

        fields = [
            'approval_id',
            'request',
            'approver',
            'level',
            'decision',
            'decided_at',
        ]


# =========================================================
# LEAVE ACCRUAL SERIALIZER
# =========================================================
class LeaveAccrualSerializer(serializers.ModelSerializer):

    class Meta:
        model = LeaveAccrual

        fields = [
            'accrual_id',
            'employee',
            'leave_type',
            'accrued_at',
            'hours_accrued',
        ]