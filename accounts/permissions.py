
from rest_framework.permissions import BasePermission, SAFE_METHODS


# =========================================================
# HR OFFICER OR READ ONLY
# =========================================================

class IsHROfficerOrReadOnly(BasePermission):
    """
    HR Officers and superusers have full access.
    Other authenticated users have read-only access.
    """

    message = "Only HR Officers can modify these records."

    def has_permission(self, request, view):
        user = request.user

        if not user or not user.is_authenticated:
            return False

        if user.is_superuser:
            return True

        if request.method in SAFE_METHODS:
            return True

        role = getattr(user, 'role', None)

        return (
            role is not None
            and role.role_name == 'HR_OFFICER'
        )


# =========================================================
# LINE MANAGER
# =========================================================

class IsLineManager(BasePermission):
    """
    Only Line Managers and superusers.
    """

    message = "Only Line Managers can perform this action."

    def has_permission(self, request, view):
        user = request.user

        if not user or not user.is_authenticated:
            return False

        if user.is_superuser:
            return True

        role = getattr(user, 'role', None)

        return (
            role is not None
            and role.role_name == 'LINE_MANAGER'
        )


# =========================================================
# HR OFFICER
# =========================================================

class IsHROfficer(BasePermission):
    """
    Only HR Officers and superusers.
    """

    message = "Only HR Officers can perform this action."

    def has_permission(self, request, view):
        user = request.user

        if not user or not user.is_authenticated:
            return False

        if user.is_superuser:
            return True

        role = getattr(user, 'role', None)

        return (
            role is not None
            and role.role_name == 'HR_OFFICER'
        )


# =========================================================
# PAYROLL ADMIN
# =========================================================

class IsPayrollAdmin(BasePermission):
    """
    Only Payroll Admins and superusers.
    """

    message = "Only Payroll Admins can perform this action."

    def has_permission(self, request, view):
        user = request.user

        if not user or not user.is_authenticated:
            return False

        if user.is_superuser:
            return True

        role = getattr(user, 'role', None)

        return (
            role is not None
            and role.role_name == 'PAYROLL_ADMIN'
        )
