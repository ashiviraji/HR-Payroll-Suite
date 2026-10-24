from django.db import models
from employees.models import Employee


class SalaryRecord(models.Model):
    salary_id = models.AutoField(primary_key=True)

    employee = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name='salary_records'
    )

    base_salary = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    effective_from = models.DateField()
    effective_to = models.DateField(
        null=True,
        blank=True
    )

    def __str__(self):
        return f"{self.employee} - {self.base_salary}"


class TaxTable(models.Model):
    tax_table_id = models.AutoField(primary_key=True)
    financial_year = models.CharField(max_length=20)
    effective_from = models.DateField()
    effective_to = models.DateField()

    def __str__(self):
        return self.financial_year


class TaxBracket(models.Model):
    bracket_id = models.AutoField(primary_key=True)

    tax_table = models.ForeignKey(
        TaxTable,
        on_delete=models.CASCADE,
        related_name='tax_brackets'
    )

    lower_bound = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    upper_bound = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True
    )

    rate = models.DecimalField(
        max_digits=5,
        decimal_places=2
    )

    def __str__(self):
        return f"{self.lower_bound} - {self.upper_bound} ({self.rate}%)"


class PayrollRun(models.Model):

    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
    ]

    run_id = models.AutoField(primary_key=True)

    tax_table = models.ForeignKey(
        TaxTable,
        on_delete=models.PROTECT,
        related_name='payroll_runs'
    )

    period = models.CharField(max_length=20)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING'
    )

    run_at = models.DateTimeField(
        null=True,
        blank=True
    )

    def __str__(self):
        return f"Payroll Run {self.run_id} - {self.period}"


class Payslip(models.Model):
    payslip_id = models.AutoField(primary_key=True)

    run = models.ForeignKey(
        PayrollRun,
        on_delete=models.PROTECT,
        related_name='payslips'
    )

    employee = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name='payslips'
    )

    gross_pay = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    tax_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    total_deductions = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    net_pay = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    pdf_path = models.CharField(
        max_length=255,
        blank=True
    )

    def __str__(self):
        return f"Payslip #{self.payslip_id} - {self.employee}"