from django.contrib import admin
from .models import (
    SalaryRecord,
    TaxTable,
    TaxBracket,
    PayrollRun,
    Payslip,
)


@admin.register(SalaryRecord)
class SalaryRecordAdmin(admin.ModelAdmin):
    list_display = (
        'salary_id',
        'employee',
        'base_salary',
        'effective_from',
        'effective_to',
    )


@admin.register(TaxTable)
class TaxTableAdmin(admin.ModelAdmin):
    list_display = (
        'tax_table_id',
        'financial_year',
        'effective_from',
        'effective_to',
    )


@admin.register(TaxBracket)
class TaxBracketAdmin(admin.ModelAdmin):
    list_display = (
        'bracket_id',
        'tax_table',
        'lower_bound',
        'upper_bound',
        'rate',
    )

    list_filter = ('tax_table',)


@admin.register(PayrollRun)
class PayrollRunAdmin(admin.ModelAdmin):
    list_display = (
        'run_id',
        'period',
        'tax_table',
        'status',
        'run_at',
    )

    list_filter = ('status', 'tax_table')


@admin.register(Payslip)
class PayslipAdmin(admin.ModelAdmin):
    list_display = (
        'payslip_id',
        'employee',
        'run',
        'gross_pay',
        'tax_amount',
        'total_deductions',
        'net_pay',
    )

    list_filter = ('run',)