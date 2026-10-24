from django.contrib import admin
from .models import (
    LeaveType,
    LeaveRequest,
    LeaveApproval,
    LeaveAccrual,
)


@admin.register(LeaveType)
class LeaveTypeAdmin(admin.ModelAdmin):
    list_display = (
        'leave_type_id',
        'name',
        'accrual_rate',
        'is_paid',
    )


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = (
        'request_id',
        'employee',
        'leave_type',
        'start_date',
        'end_date',
        'status',
    )

    list_filter = ('status', 'leave_type')


@admin.register(LeaveApproval)
class LeaveApprovalAdmin(admin.ModelAdmin):
    list_display = (
        'approval_id',
        'request',
        'approver',
        'level',
        'decision',
        'decided_at',
    )

    list_filter = ('level', 'decision')


@admin.register(LeaveAccrual)
class LeaveAccrualAdmin(admin.ModelAdmin):
    list_display = (
        'accrual_id',
        'employee',
        'leave_type',
        'accrued_at',
        'hours_accrued',
    )