
from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    SalaryRecordViewSet,
    TaxTableViewSet,
    TaxBracketViewSet,
    PayrollRunViewSet,
    PayslipViewSet,
)

from .web_views import (
    salary_record_list,
    salary_record_create,
    salary_record_update,
)


# =========================================================
# 1. REST API ROUTES
# =========================================================

router = DefaultRouter()

router.register(
    r'salary-records',
    SalaryRecordViewSet,
    basename='salary-record'
)

router.register(
    r'tax-tables',
    TaxTableViewSet,
    basename='tax-table'
)

router.register(
    r'tax-brackets',
    TaxBracketViewSet,
    basename='tax-bracket'
)

router.register(
    r'payroll-runs',
    PayrollRunViewSet,
    basename='payroll-run'
)

router.register(
    r'payslips',
    PayslipViewSet,
    basename='payslip'
)


# =========================================================
# 2. SALARY MANAGEMENT WEB ROUTES
# =========================================================

urlpatterns = [
    path(
        'salary-management/',
        salary_record_list,
        name='salary_record_list'
    ),

    path(
        'salary-management/create/',
        salary_record_create,
        name='salary_record_create'
    ),

    path(
        'salary-management/<int:salary_id>/edit/',
        salary_record_update,
        name='salary_record_update'
    ),
]


# =========================================================
# 3. INCLUDE REST API ROUTES
# =========================================================

urlpatterns += router.urls
