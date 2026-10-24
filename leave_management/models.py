from django.db import models
from employees.models import Employee


class LeaveType(models.Model):
    leave_type_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100, unique=True)
    accrual_rate = models.DecimalField(
        max_digits=6,
        decimal_places=2
    )
    is_paid = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class LeaveRequest(models.Model):

    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('MANAGER_APPROVED', 'Manager Approved'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]

    request_id = models.AutoField(primary_key=True)

    employee = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name='leave_requests'
    )

    leave_type = models.ForeignKey(
        LeaveType,
        on_delete=models.PROTECT,
        related_name='leave_requests'
    )

    start_date = models.DateField()
    end_date = models.DateField()

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default='PENDING'
    )

    def __str__(self):
        return f"Leave #{self.request_id} - {self.employee}"


class LeaveApproval(models.Model):

    DECISION_CHOICES = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]

    approval_id = models.AutoField(primary_key=True)

    request = models.ForeignKey(
        LeaveRequest,
        on_delete=models.CASCADE,
        related_name='approvals'
    )

    approver = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name='leave_approvals'
    )

    level = models.PositiveIntegerField()

    decision = models.CharField(
        max_length=20,
        choices=DECISION_CHOICES,
        default='PENDING'
    )

    decided_at = models.DateTimeField(
        null=True,
        blank=True
    )

    def __str__(self):
        return f"Approval #{self.approval_id} - Level {self.level}"


class LeaveAccrual(models.Model):
    accrual_id = models.AutoField(primary_key=True)

    employee = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name='leave_accruals'
    )

    leave_type = models.ForeignKey(
        LeaveType,
        on_delete=models.PROTECT,
        related_name='leave_accruals'
    )

    accrued_at = models.DateField()

    hours_accrued = models.DecimalField(
        max_digits=8,
        decimal_places=2
    )

    def __str__(self):
        return f"{self.employee} - {self.leave_type}"