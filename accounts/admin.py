from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Role, UserAccount


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = (
        'role_id',
        'role_name',
    )


@admin.register(UserAccount)
class UserAccountAdmin(UserAdmin):
    list_display = (
        'user_id',
        'username',
        'employee',
        'role',
        'is_active',
        'is_staff',
    )

    fieldsets = UserAdmin.fieldsets + (
        (
            'HR Payroll Information',
            {
                'fields': (
                    'employee',
                    'role',
                )
            },
        ),
    )

    add_fieldsets = UserAdmin.add_fieldsets + (
        (
            'HR Payroll Information',
            {
                'fields': (
                    'employee',
                    'role',
                )
            },
        ),
    )