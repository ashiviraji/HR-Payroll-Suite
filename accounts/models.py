
from django.db import models
from django.contrib.auth.models import AbstractUser
from employees.models import Employee


# =========================================================
# ROLE MODEL
# =========================================================

class Role(models.Model):

    role_id = models.AutoField(primary_key=True)

    ROLE_CHOICES = [
        ('EMPLOYEE', 'Employee'),
        ('LINE_MANAGER', 'Line Manager'),
        ('HR_OFFICER', 'HR Officer'),
        ('PAYROLL_ADMIN', 'Payroll Admin'),
    ]

    role_name = models.CharField(
        max_length=30,
        choices=ROLE_CHOICES,
        unique=True
    )

    def __str__(self):
        return self.get_role_name_display()


# =========================================================
# USER ACCOUNT MODEL
# =========================================================

class UserAccount(AbstractUser):

    user_id = models.AutoField(primary_key=True)

    employee = models.OneToOneField(
        Employee,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='user_account'
    )

    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='user_accounts'
    )

    def __str__(self):
        return self.username
