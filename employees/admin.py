from django.contrib import admin
from .models import Department, Employee


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = (
        'department_id',
        'name',
    )


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = (
        'employee_id',
        'first_name',
        'last_name',
        'email',
        'department',
        'manager',
        'hire_date',
        'employment_status',
    )

    search_fields = (
        'first_name',
        'last_name',
        'email',
    )

    list_filter = (
        'department',
        'employment_status',
    )